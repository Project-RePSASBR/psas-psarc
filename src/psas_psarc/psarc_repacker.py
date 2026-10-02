import hashlib
import logging
import struct
import zlib
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Util import Counter

from psas_psarc._common import (
    ps3_retail_key,
    psarc_archive_header,
    psarc_compression_magic,
    psarc_header_magic,
    psarc_toc_entry,
)

_logger = logging.getLogger(__package__)


class _PsarcRepacker:
    """
    Utility class for repacking PSARC archives from extracted content
    for PlayStation All-Stars Battle Royale for the PlayStation Vita and PlayStation 3.
    """

    def __init__(self, input_dir: Path, output_file: Path, *, encrypt: bool = False, max_block_size: int = 65536):
        """
        Initialize a new PSARC repacker.

        :param input_dir: the directory containing the data to convert to a PSARC archive
        :type input_dir: Path
        :param output_file: the path to write the resulting PSARC file archive to
        :type output_file: Path
        :param encrypt: encrypt the PSARC archive for use with PS3 retail, defaults to False
        :type encrypt: bool, optional
        :param max_block_size: the maximum size of a compressed block, defaults to 65536
        :type max_block_size: int, optional
        """

        self.input_dir = Path(input_dir) if isinstance(input_dir, str) else input_dir
        self.output_file = Path(output_file) if isinstance(output_file, str) else output_file
        self.encrypt = encrypt
        self.max_block_size = max_block_size
        _logger.debug(
            "Initializing PSARC repacker for '%s' -> '%s' (encrypt=%s, max_block_size=%d)",
            self.input_dir,
            self.output_file,
            self.encrypt,
            self.max_block_size,
        )

    def _block_type_for_max_block_size(self) -> int:
        """Return the byte width needed to store block lengths."""

        block_type = 1
        i = 256
        while i < self.max_block_size:
            i *= 256
            block_type = (block_type + 1) & 0xFF
        return block_type

    def _normalize_relative_path(self, path: Path) -> str:
        """Return a PSARC-style relative path with a leading slash."""

        rel = path.relative_to(self.input_dir).as_posix()
        normalized = f"/{rel}"
        _logger.debug("Normalizing path '%s' to '%s'", path, normalized)
        return normalized

    def _chunk_bytes(self, data: bytes) -> list[bytes]:
        """Split a bytestream into chunks no larger than max_block_size."""

        if not data:
            return [b""]
        return [data[offset : offset + self.max_block_size] for offset in range(0, len(data), self.max_block_size)]

    def _manifest_bytes(self, paths: list[str]) -> bytes:
        """Serialize the archive manifest. PSARC manifests are newline-delimited without a trailing newline."""

        if not paths:
            return b""
        return "\n".join(paths).encode("utf-8")

    def _serialize_header(self, toc_entries: int, toc_length: int) -> bytes:
        """Serialize the PSARC archive header."""

        header = {
            "magic": psarc_header_magic,
            "major_version": 1,
            "minor_version": 4,
            "compression_type": psarc_compression_magic,
            "toc_length": toc_length,
            "toc_entry_size": 30,
            "toc_entries": toc_entries,
            "max_block_size": self.max_block_size,
            "archive_flags": 2,
        }
        return psarc_archive_header.build(header)

    def _serialize_toc_entry(
        self, name_digest: bytes, block_index: int, uncompressed_size: int, file_offset: int
    ) -> bytes:
        """Serialize a PSARC TOC entry."""

        entry = {
            "name_digest": name_digest,
            "block_index": block_index,
            "uncompressed_size": uncompressed_size.to_bytes(5, byteorder="big"),
            "file_offset": file_offset.to_bytes(5, byteorder="big"),
        }
        return psarc_toc_entry.build(entry)

    def _compress_block(self, raw_block: bytes, block_index: int) -> bytes:
        """Compress a block and optionally encrypt it for PS3 retail archives."""

        if self.encrypt:
            _logger.debug("Encrypting PS3 retail block %d (%d bytes)", block_index, len(raw_block))
            comp = zlib.compressobj(level=9, wbits=-15)
            compressed = comp.compress(raw_block) + comp.flush()
            header = struct.pack(">H", (block_index + 1) & 0xFFFF)
            prefix = (
                b"\xde\xad\xbe\xef"
                + struct.pack(">I", len(header) + len(compressed))
                + struct.pack(">I", int.from_bytes(header, byteorder="big"))
            )
            ctr = Counter.new(32, prefix=prefix, initial_value=0)
            aes_ctx = AES.new(ps3_retail_key, AES.MODE_CTR, counter=ctr)
            return header + aes_ctx.encrypt(compressed)

        _logger.debug("Compressing block %d (%d bytes)", block_index, len(raw_block))
        return zlib.compress(raw_block)

    def _ordered_files(self, file_order: list[str] | None = None) -> list[Path]:
        """Return the files to include in the archive manifest."""

        by_rel = {self._normalize_relative_path(path): path for path in self.input_dir.rglob("*") if path.is_file()}
        _logger.debug("Found %d files in directory '%s'", len(by_rel), self.input_dir)
        if file_order is None:
            ordered_names = sorted(by_rel)
            _logger.debug("Using default sorted file order for manifest")
        else:
            ordered_names = list(file_order)
            missing = [name for name in ordered_names if name not in by_rel]
            if missing:
                _logger.error("Missing files for archive order: %s", ", ".join(missing[:10]))
                raise ValueError(f"Missing files for archive order: {', '.join(missing[:10])}")
            ordered_names.extend(name for name in sorted(by_rel) if name not in ordered_names)
            _logger.debug("Using explicit file order for manifest (%d entries)", len(ordered_names))
        return [by_rel[name] for name in ordered_names]

    def repack(self, file_order: list[str] | None = None):
        """
        Repack the PSARC archive from the input directory.

        :param file_order: an optional list of relative paths to include in the archive manifest, defaults to None
        :type file_order: list[str] | None, optional
        """

        files = self._ordered_files(file_order=file_order)
        manifest_paths = [self._normalize_relative_path(path) for path in files]
        manifest_bytes = self._manifest_bytes(manifest_paths)
        _logger.info("Preparing PSARC manifest with %d entries (%d bytes)", len(manifest_paths), len(manifest_bytes))

        block_payloads: list[bytes] = []
        block_lengths: list[int] = []
        toc_entries: list[tuple[bytes, int, int, int, int]] = []

        block_index = 0
        for chunk in self._chunk_bytes(manifest_bytes):
            block_payloads.append(self._compress_block(chunk, block_index=block_index))
            block_lengths.append(len(block_payloads[-1]))
            _logger.info("Manifest block %d compressed to %d bytes", block_index, block_lengths[-1])
            block_index += 1
        toc_entries.append((b"\x00" * 16, 0, len(manifest_bytes), 0, len(self._chunk_bytes(manifest_bytes))))

        for path in files:
            raw = path.read_bytes()
            file_chunks = self._chunk_bytes(raw)
            file_start_index = block_index
            _logger.info(
                "Processing file '%s' (%d bytes, %d chunks)",
                self._normalize_relative_path(path),
                len(raw),
                len(file_chunks),
            )
            for chunk in file_chunks:
                block_payloads.append(self._compress_block(chunk, block_index=block_index))
                block_lengths.append(len(block_payloads[-1]))
                _logger.debug("File block %d compressed to %d bytes", block_index, block_lengths[-1])
                block_index += 1
            toc_entries.append(
                (
                    hashlib.md5(self._normalize_relative_path(path).encode("utf-8")).digest(),
                    file_start_index,
                    len(raw),
                    0,
                    len(file_chunks),
                )
            )

        block_type = self._block_type_for_max_block_size()
        toc_length = 32 + (len(toc_entries) * 30) + (len(block_lengths) * block_type)
        _logger.info(
            "Built TOC for %d entries with %d blocks (%d bytes total)", len(toc_entries), len(block_lengths), toc_length
        )

        data_offset = toc_length
        file_offset = data_offset
        resolved_toc: list[tuple[bytes, int, int, int]] = []
        for name_digest, block_index_start, uncompressed_size, _, block_count in toc_entries:
            offset = file_offset
            file_offset += sum(block_lengths[block_index_start : block_index_start + block_count])
            resolved_toc.append((name_digest, block_index_start, uncompressed_size, offset))

        archive = bytearray(self._serialize_header(len(toc_entries), toc_length))
        for name_digest, block_index_start, uncompressed_size, file_offset in resolved_toc:
            archive += self._serialize_toc_entry(name_digest, block_index_start, uncompressed_size, file_offset)
        for block_size in block_lengths:
            archive += block_size.to_bytes(block_type, byteorder="big")
        archive += b"".join(block_payloads)

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with self.output_file.open("wb") as fh:
            fh.write(archive)
        _logger.info("Wrote repacked PSARC archive to '%s' (%d bytes)", self.output_file, len(archive))


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

    _logger.info("Repacking PSARC archive from '%s' to '%s'", input_dir, output_file)

    repacker = _PsarcRepacker(input_dir, output_file, encrypt=encrypt, max_block_size=max_block_size)
    repacker.repack(file_order=file_order)
