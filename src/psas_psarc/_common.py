from construct import Array, Byte, Const, Int16ub, Int32ub, Struct

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
