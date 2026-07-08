import argparse
import sys


def _add_extract_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add arguments for PSARC extraction to the given parser.

    :parameter parser: command-line argument parser
    :type parser: argparse.ArgumentParser
    """


def _add_repack_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add arguments for PSARC repacking to the given parser.

    :parameter parser: command-line argument parser
    :type parser: argparse.ArgumentParser
    """


def get_parser() -> argparse.ArgumentParser:
    """
    Construct parser for parsing command-line arguments.

    :returns: command-line argument parser
    :rtype: argparse.ArgumentParser
    """

    parser = argparse.ArgumentParser(
        prog="psas-psarc",
        description=(
            "Command-line utility for extracting and repacking PSARC archives for "
            "PlayStation All-Stars Battle Royale for the Playstation 3 and Playstation Vita."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # For PSARC extraction / decryption
    extract_parser = subparsers.add_parser("extract", help="Extract (and decrypt) PSARC archive")
    _add_extract_arguments(extract_parser)

    # For PSARC repacking / encryption
    repack_parser = subparsers.add_parser("repack", help="Repack PSARC archive")
    _add_repack_arguments(repack_parser)

    return parser


def main() -> int:
    # parser = get_parser()
    # args = parser.parse_args()

    return 0


if __name__ == "__main__":
    sys.exit(main())
