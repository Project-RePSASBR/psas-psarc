# PSAS PSARC

PSAS PSARC is a light-weight Python package for managing PSARC archives for PlayStation All-Stars Battle Royale (PSAS). This package has support for both extracting and repacking PSARC archives for both the retail PS3 and Vita versions of the game. PSARC archives for the retail PS3 version are encrypted and this package contains special logic for decrypting retail PSARC archives and then repacking them into their original encrypted format.

## Installation
Install PSAS PSARC via `pip` from [PyPI](https://pypi.org):

```bash
pip install psas-psarc
```

## Command-Line Utility
PSAS PSARC can be used as a simple command-line utility once installed. See the help output below for example usage.

```bash
$ psas-psarc -h
usage: psas-psarc [-h] {extract,repack} ...

Command-line utility for extracting and repacking PSARC archives for PlayStation All-Stars Battle Royale for the Playstation 3 and Playstation Vita.

positional arguments:
  {extract,repack}
    extract         Extract (and decrypt) PSARC archive
    repack          Repack PSARC archive

options:
  -h, --help        show this help message and exit
```

```bash
$ psas-psarc extract -h
usage: psas-psarc extract [-h] [-v | --verbose | --no-verbose] -p PSARC [-o OUTPUT]

options:
  -h, --help            show this help message and exit

generic arguments:
  -v, --verbose, --no-verbose
                        Enable verbose logging output (default: False)

psarc extraction arguments:
  -p PSARC, --psarc PSARC
                        Path to PSARC archive to extract
  -o OUTPUT, --output OUTPUT
                        Output directory to write extracted PSARC archive contents to (default: current directory)
```

```bash
$ psas-psarc repack -h
usage: psas-psarc repack [-h] [-v | --verbose | --no-verbose] -i INPUT -o OUTPUT [-e | --encrypt | --no-encrypt]

options:
  -h, --help            show this help message and exit

generic arguments:
  -v, --verbose, --no-verbose
                        Enable verbose logging output (default: False)

psarc repack arguments:
  -i INPUT, --input INPUT
                        Path to directory containing files to repack into PSARC archive
  -o OUTPUT, --output OUTPUT
                        Output file to write repacked PSARC archive to
  -e, --encrypt, --no-encrypt
                        Encrypt blobs when repacking PSARC archive for use with PS3 version (default: False)
```

## Usage
PSAS PSARC can be imported and used inside of your own custom Python scripts. Example usage is shown below.

```python
from psas_psarc import *

output_dir = "my_psarc_output"
my_psarc_archive = "patch.psarc"

# Extract the contents of patch.psarc to the path my_psarc_output
extract_psas_psarc(my_psarc_archive, output_dir)

# Extract individual files (my_test_file in the below example) from a given archive
my_file_bytes = extract_file_from_psas_psarc(my_psarc_archive, "my_test_file")

# Modify files from the extracted archive
...

# Repack the archive, reencrypt if using archives with the retail PS3 version
repack_psas_psarc("my_psarc_output/patch", "my_psarc_output/patch_repacked.psarc", encrypt=True)
```

## Credits
Thanks to Hazza for developing the intial Python script for PSARC archive extraction.