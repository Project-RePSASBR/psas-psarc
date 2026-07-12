import hashlib
import logging
import struct
import zlib
from pathlib import Path

from construct import Array, Byte, Const, Container, Int16ub, Int32ub, Struct
from Crypto.Cipher import AES
from Crypto.Util import Counter

_logger = logging.getLogger(__package__)


class _PsarcArchiveMetadata:
    """
    Utility class for tracking metadata associated with a given PSARC archive.
    """

    def __init__(
        self,
        header: Container,
        block_type: int,
        toc_entries: list[Container],
        block_lengths: list[int],
    ) -> None:
        """
        _PsarcArchiveMetadata constructor.

        :param header: parsed PSARC archive header container
        :type header: construct.lib.containers.Container
        :param block_type: number of bytes needed to represent the size of a compressed block
        :type block_type: int
        :param toc_entries: list of parsed PSARC archive TOC entry containers
        :type toc_entries: list[construct.lib.containers.Container]
        :param block_lengths: list of sizes of each compressed block in the PSARC archive
        :type block_lengths: list[int]
        """

        self.header = header
        self.block_type = block_type
        self.toc_entries = toc_entries
        self.block_lengths = block_lengths


class _PsarcExtractor:
    """
    Utility class for analyzing and extracting and analyzing PSARC archives
    for PlayStation All-Stars Battle Royale for the PlayStation Vita and PlayStation 3.
    """

    # PSARC archive header magic bytes
    psarc_header_magic = b"PSAR"

    # PSARC archive compression type magic bytes
    psarc_compression_magic = b"zlib"

    # PSARC archive header struct definition
    psarc_archive_header = Struct(
        "magic" / Const(psarc_header_magic),
        "major_version" / Int16ub,
        "minor_version" / Int16ub,
        "compression_type" / Const(psarc_compression_magic),
        "toc_length" / Int32ub,
        "toc_entry_size" / Int32ub,
        "toc_entries" / Int32ub,
        "max_block_size" / Int32ub,
        "archive_flags" / Int32ub,
    )

    # PSARC archive TOC entry struct definition
    psarc_toc_entry = Struct(
        "name_digest" / Array(16, Byte),
        "block_index" / Int32ub,
        "uncompressed_size" / Array(5, Byte),
        "file_offset" / Array(5, Byte),
    )

    # Decryption key for retail PS3 archives
    ps3_retail_key = bytes.fromhex("7a7fce1f558e39a119412637923de935da7a4d41b7cc35286f56f87ce9dbc392")

    def __init__(self, psarc_path: Path) -> None:
        """
        _PsarcExtractor constructor.

        :param psarc_path: path to the PSARC archive to extract
        :type psarc_path: Path
        :raises: ValueError: if the provided PSARC archive path is invalid or does not exist
        """

        if not psarc_path.is_file() or psarc_path.suffix != ".psarc":
            raise ValueError(f"Provided path to PSARC archive '{psarc_path}' is invalid.")

        self.psarc_path = psarc_path
        self.psarc = self.psarc_path.name
        with open(self.psarc_path, "rb") as f:
            self.raw_psarc = f.read()

        self._analyze_psarc_archive()
        self._read_psarc_manifest()

    def _analyze_psarc_archive(self) -> None:
        """
        Analyze a PSARC archive by reading its header and TOC entries.
        """

        # Read the PSARC archive header
        header = self.psarc_archive_header.parse(self.raw_psarc[0 : self.psarc_archive_header.sizeof()])
        _logger.debug("Reading PSARC archive header for '%s':", self.psarc)
        for key, value in header.items():
            if key == "_io":
                continue
            _logger.debug("  %s: %s", key, value)

        # Get the number of bytes needed to indicate the size of a compressed block
        block_type = 1
        i = 256
        while i < header.max_block_size:
            i *= 256
            block_type = (block_type + 1) & 0xFF

        # Read in the archive Table of Contents (TOC) entries
        toc_entries = []
        toc_offset = self.psarc_archive_header.sizeof()
        for i in range(header.toc_entries):
            toc_entry_offset = toc_offset + (i * header.toc_entry_size)
            toc_entry = self.psarc_toc_entry.parse(
                self.raw_psarc[toc_entry_offset : toc_entry_offset + header.toc_entry_size]
            )

            # uncompressed_size and file_offset are 5-byte arrays inside of struct definition,
            # convert them to integers for easier processing
            toc_entry.uncompressed_size = int.from_bytes(toc_entry.uncompressed_size, byteorder="big")
            toc_entry.file_offset = int.from_bytes(toc_entry.file_offset, byteorder="big")

            _logger.debug("Reading ToC entry #%d from PSARC archive:", i + 1)
            _logger.debug("  name_digest: %s", bytes(toc_entry.name_digest).hex())
            _logger.debug("  block_index: 0x%x", toc_entry.block_index)
            _logger.debug("  uncompressed_size: 0x%x", toc_entry.uncompressed_size)
            _logger.debug("  file_offset: 0x%x", toc_entry.file_offset)
            toc_entries.append(toc_entry)

        # Get the size of each compressed block
        block_lengths = []
        block_size_table_offset = toc_offset + (header.toc_entries * header.toc_entry_size)
        num_blocks = (header.toc_length - block_size_table_offset) // block_type
        for i in range(num_blocks):
            block_length_offset = block_size_table_offset + (i * block_type)
            block_length_bytes = self.raw_psarc[block_length_offset : block_length_offset + block_type]
            block_length = int.from_bytes(block_length_bytes, byteorder="big")
            block_lengths.append(block_length)

        self.metadata = _PsarcArchiveMetadata(header, block_type, toc_entries, block_lengths)

    def _decrypt_body(self, block: bytes) -> bytes:
        """
        Decrypt PSARC archive data block for retail PS3 archives.

        :param block: encrypted data block
        :type block: bytes
        :return: decrypted (ZLIB compressed) data block
        :rtype: bytes
        """

        hdr = (block[0] << 8) | block[1]
        prefix = b"\xde\xad\xbe\xef" + struct.pack(">I", len(block)) + struct.pack(">I", hdr)
        ctr = Counter.new(32, prefix=prefix, initial_value=0)
        aes_ctx = AES.new(self.ps3_retail_key, AES.MODE_CTR, counter=ctr)

        return aes_ctx.decrypt(block[2:])

    def _inflate_entry(self, index: int) -> bytes:
        """
        Inflate a PSARC archive ToC entry.

        :param index: TOC index of the entry to inflate
        :type index: int
        :return: inflated entry data
        :rtype: bytes
        """

        inflated = b""

        file_offset = self.metadata.toc_entries[index].file_offset
        block_index = self.metadata.toc_entries[index].block_index
        expected_uncompressed_size = self.metadata.toc_entries[index].uncompressed_size

        while len(inflated) < expected_uncompressed_size:
            remaining = expected_uncompressed_size - len(inflated)
            block_size = self.metadata.block_lengths[block_index]
            input_chunk = self.raw_psarc[file_offset : file_offset + block_size]

            if block_size == remaining:
                inflated += input_chunk
            # ZLIB compressed blob
            elif input_chunk[:1] == b"\x78":
                _logger.debug(
                    "Decompressing unencrypted ZLIB block %d for ToC entry %d...",
                    block_index,
                    index,
                )
                inflated += zlib.decompress(input_chunk)
            # Retail PS3 encrypted blob
            else:
                decrypted_block = self._decrypt_body(input_chunk)
                inflated += zlib.decompress(decrypted_block, -15)

            block_index += 1
            file_offset += block_size

        return inflated

    def _read_psarc_manifest(self) -> None:
        """
        Read the PSARC archive manifest entry.
        """

        # The manifest should always correspond to the first ToC entry
        raw_manifest = self._inflate_entry(0)
        raw_filenames = raw_manifest.splitlines()

        self.manifest = []
        for filename in raw_filenames:
            self.manifest.append(filename.decode("utf-8"))

    def get_manifest(self) -> list[str]:
        """
        Read the PSARC archive manifest.

        :returns: list of filenames in the PSARC archive
        :rtype: list[str]
        """

        return self.manifest

    def extract_single_file(self, filename: str) -> bytes:
        """
        Extract a single file from the PSARC archive.

        :param filename: filename to extract from PSARC archive
        :type filename: str
        :returns: raw decompressed bytes from file in PSARC archive
        :rtype: bytes
        :raises ValueError: if provided filename is not in the PSARC archive
        """

        if filename not in self.manifest:
            raise ValueError(f"Provided filename '{filename}' does not exist in PSARC archive {self.psarc}!")

        toc_entry_index = -1
        md5_hash = hashlib.md5(filename.encode("utf-8")).hexdigest()
        for i, toc_entry in enumerate(self.metadata.toc_entries):
            if bytes(toc_entry.name_digest).hex() == md5_hash:
                toc_entry_index = i
                break

        if toc_entry_index < 0:
            raise ValueError(f"ToC entry for filename '{filename}' not found in PSARC archive {self.psarc}!")

        _logger.info("Extracting filename %s from PSARC archive %s...", filename, self.psarc)
        return self._inflate_entry(toc_entry_index)

    def extract_all(self, output_dir: str = ".") -> None:
        """
        Extract all the contents of the PSARC archive to the provided output directory.

        :param output_dir: name of output directory to write extracted contents to
        :type output_dir: str
        :raises ValueError: if provided output directory does not exist
        """

        if not output_dir.is_dir():
            raise ValueError(f"Provided output directory '{output_dir}' does not exist!")

        psarc_root = output_dir / self.psarc_path.stem
        for filename in self.manifest:
            _logger.info("Extracting filename %s from PSARC archive %s...", filename, self.psarc)
            filepath = psarc_root / filename[1:]
            filepath_parent = filepath.parent
            filepath_parent.mkdir(parents=True, exist_ok=True)

            raw_file = self.extract_single_file(filename)
            with open(filepath, "wb") as f:
                f.write(raw_file)


def extract_psas_psarc(psarc_path: Path, output_dir: Path) -> None:
    """
    Extract the contents of a Playstation All-Stars Battle Royale PSARC archive to a specified output directory.

    :param psarc_path: path to the PSARC archive to extract
    :type psarc_path: Path
    :param output_dir: path to write the extracted contents of the PSARC archive to
    :type output_dir: Path
    """

    if not output_dir.is_dir():
        raise ValueError(f"Provided output directory '{output_dir}' does not exist.")

    _logger.info("Extracting PSARC archive: %s to output directory: %s", psarc_path, output_dir)

    extractor = _PsarcExtractor(psarc_path)
    extractor.extract_all(output_dir)
