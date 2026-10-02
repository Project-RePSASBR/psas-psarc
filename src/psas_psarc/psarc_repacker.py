import hashlib
import logging
import struct
import zlib
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Util import Counter

from psas_psarc.psarc_extractor import _PsarcExtractor

_logger = logging.getLogger(__package__)


def _block_type_for_max_block_size(max_block_size: int) -> int:
    """Return the byte width needed to store block lengths."""

    block_type = 1
    i = 256
    while i < max_block_size:
        i *= 256
        block_type = (block_type + 1) & 0xFF
    return block_type


def _normalize_relative_path(path: Path, root: Path) -> str:
    """Return a PSARC-style relative path with a leading slash."""

    rel = path.relative_to(root).as_posix()
    return f"/{rel}"


def _chunk_bytes(data: bytes, max_chunk_size: int) -> list[bytes]:
    """Split a bytestream into chunks no larger than max_chunk_size."""

    if not data:
        return [b""]
    return [data[offset : offset + max_chunk_size] for offset in range(0, len(data), max_chunk_size)]


def _manifest_bytes(paths: list[str]) -> bytes:
    """Serialize the archive manifest. PSARC manifests are newline-delimited without a trailing newline."""

    if not paths:
        return b""
    return "\n".join(paths).encode("utf-8")


def _serialize_header(toc_entries: int, toc_length: int) -> bytes:
    """Serialize the PSARC archive header."""

    header = {
        "magic": b"PSAR",
        "major_version": 1,
        "minor_version": 4,
        "compression_type": b"zlib",
        "toc_length": toc_length,
        "toc_entry_size": 30,
        "toc_entries": toc_entries,
        "max_block_size": 65536,
        "archive_flags": 2,
    }
    return _PsarcExtractor.psarc_archive_header.build(header)


def _serialize_toc_entry(name_digest: bytes, block_index: int, uncompressed_size: int, file_offset: int) -> bytes:
    """Serialize a PSARC TOC entry."""

    entry = {
        "name_digest": name_digest,
        "block_index": block_index,
        "uncompressed_size": uncompressed_size.to_bytes(5, byteorder="big"),
        "file_offset": file_offset.to_bytes(5, byteorder="big"),
    }
    return _PsarcExtractor.psarc_toc_entry.build(entry)


def _compress_block(raw_block: bytes, *, encrypt: bool, block_index: int) -> bytes:
    """Compress a block and optionally encrypt it for PS3 retail archives."""

    if encrypt:
        comp = zlib.compressobj(level=9, wbits=-15)
        compressed = comp.compress(raw_block) + comp.flush()
        header = struct.pack(">H", (block_index + 1) & 0xFFFF)
        prefix = (
            b"\xde\xad\xbe\xef"
            + struct.pack(">I", len(header) + len(compressed))
            + struct.pack(">I", int.from_bytes(header, byteorder="big"))
        )
        ctr = Counter.new(32, prefix=prefix, initial_value=0)
        aes_ctx = AES.new(_PsarcExtractor.ps3_retail_key, AES.MODE_CTR, counter=ctr)
        return header + aes_ctx.encrypt(compressed)

    return zlib.compress(raw_block)


def _ordered_files(input_dir: Path, file_order: list[str] | None = None) -> list[Path]:
    """Return the files to include in the archive manifest."""

    by_rel = {_normalize_relative_path(path, input_dir): path for path in input_dir.rglob("*") if path.is_file()}
    if file_order is None:
        ordered_names = sorted(by_rel)
    else:
        ordered_names = list(file_order)
        missing = [name for name in ordered_names if name not in by_rel]
        if missing:
            raise ValueError(f"Missing files for archive order: {', '.join(missing[:10])}")
        ordered_names.extend(name for name in sorted(by_rel) if name not in ordered_names)
    return [by_rel[name] for name in ordered_names]


def repack_psas_psarc(
    input_dir: Path,
    output_file: Path,
    *,
    encrypt: bool = False,
    max_block_size: int = 65536,
    file_order: list[str] | None = None,
) -> Path:
    """Create a PSARC archive from a directory containing extracted PSARC content.

    :param input_dir: the directory containing the data to convert to a PSARC archive
    :type input_dir: Path
    :param output_file: the path to write the resulting PSARC file archive to
    :type output_file: Path
    :param encrypt: encrypt the PSARC archive for use with PS3 retail, defaults to False
    :type encrypt: bool, optional
    :param max_block_size: the maximum size of a compressed block, defaults to 65536
    :type max_block_size: int, optional
    :param file_order: an optional list of relative paths to include in the archive manifest, defaults to None
    :type file_order: list[str] | None, optional
    """

    input_dir = Path(input_dir) if isinstance(input_dir, str) else input_dir
    output_file = Path(output_file) if isinstance(output_file, str) else output_file

    if not input_dir.is_dir():
        raise ValueError(f"Provided input directory '{input_dir}' does not exist or is not a directory!")

    files = _ordered_files(input_dir, file_order=file_order)
    manifest_paths = [_normalize_relative_path(path, input_dir) for path in files]
    manifest_bytes = _manifest_bytes(manifest_paths)

    block_payloads: list[bytes] = []
    block_lengths: list[int] = []
    toc_entries: list[tuple[bytes, int, int, int, int]] = []

    block_index = 0
    for chunk in _chunk_bytes(manifest_bytes, max_block_size):
        block_payloads.append(_compress_block(chunk, encrypt=encrypt, block_index=block_index))
        block_lengths.append(len(block_payloads[-1]))
        block_index += 1
    toc_entries.append((b"\x00" * 16, 0, len(manifest_bytes), 0, len(_chunk_bytes(manifest_bytes, max_block_size))))

    for path in files:
        raw = path.read_bytes()
        file_chunks = _chunk_bytes(raw, max_block_size)
        file_start_index = block_index
        for chunk in file_chunks:
            block_payloads.append(_compress_block(chunk, encrypt=encrypt, block_index=block_index))
            block_lengths.append(len(block_payloads[-1]))
            block_index += 1
        toc_entries.append(
            (
                hashlib.md5(_normalize_relative_path(path, input_dir).encode("utf-8")).digest(),
                file_start_index,
                len(raw),
                0,
                len(file_chunks),
            )
        )

    block_type = _block_type_for_max_block_size(max_block_size)
    toc_length = 32 + (len(toc_entries) * 30) + (len(block_lengths) * block_type)

    data_offset = toc_length
    file_offset = data_offset
    resolved_toc: list[tuple[bytes, int, int, int]] = []
    for name_digest, block_index_start, uncompressed_size, _, block_count in toc_entries:
        offset = file_offset
        file_offset += sum(block_lengths[block_index_start : block_index_start + block_count])
        resolved_toc.append((name_digest, block_index_start, uncompressed_size, offset))

    archive = bytearray(_serialize_header(len(toc_entries), toc_length))
    for name_digest, block_index_start, uncompressed_size, file_offset in resolved_toc:
        archive += _serialize_toc_entry(name_digest, block_index_start, uncompressed_size, file_offset)
    for block_size in block_lengths:
        archive += block_size.to_bytes(block_type, byteorder="big")
    archive += b"".join(block_payloads)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("wb") as fh:
        fh.write(archive)

    return output_file
