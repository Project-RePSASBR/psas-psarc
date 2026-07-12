#!/usr/bin/env python3

import argparse
import logging
import sys
from pathlib import Path

import argcomplete

from psas_psarc._logging_classes import BColors, setup_loggers
from psas_psarc.psarc_extractor import extract_psas_psarc


def _add_generic_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add generic arguments to the given parser.

    :param parser: command-line argument parser
    :type parser: argparse.ArgumentParser
    """

    generic_args = parser.add_argument_group("generic arguments")
    generic_args.add_argument(
        "-v", "--verbose", action=argparse.BooleanOptionalAction, help="Enable verbose logging output (default: False)"
    )


def _add_extract_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add arguments for PSARC extraction to the given parser.

    :param parser: command-line argument parser
    :type parser: argparse.ArgumentParser
    """

    extraction_args = parser.add_argument_group("psarc extraction arguments")

    extraction_args.add_argument("-p", "--psarc", type=Path, required=True, help="Path to PSARC archive to extract")
    extraction_args.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("."),
        help="Output directory to write extracted PSARC archive contents to (default: current directory)",
    )


def _add_repack_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add arguments for PSARC repacking to the given parser.

    :param parser: command-line argument parser
    :type parser: argparse.ArgumentParser
    """

    repack_args = parser.add_argument_group("psarc repack arguments")
    repack_args.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Path to directory containing files to repack into PSARC archive",
    )
    repack_args.add_argument(
        "-e",
        "--encrypt",
        action=argparse.BooleanOptionalAction,
        help="Encrypt blobs when repacking PSARC archive for use with PS3 version (default: False)",
    )


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
    _add_generic_arguments(extract_parser)
    _add_extract_arguments(extract_parser)

    # For PSARC repacking / encryption
    repack_parser = subparsers.add_parser("repack", help="Repack PSARC archive")
    _add_generic_arguments(repack_parser)
    _add_repack_arguments(repack_parser)

    return parser


def main() -> int:
    parser = get_parser()
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    setup_loggers(__package__, level=logging.INFO if not args.verbose else logging.DEBUG)

    try:
        if args.command == "extract":
            extract_psas_psarc(args.psarc.resolve(), args.output.resolve())
        elif args.command == "repack":
            pass
    except Exception as e:
        print(f"{BColors.FAIL}Error: {e}{BColors.ENDC}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
