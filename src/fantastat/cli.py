from __future__ import annotations


import sys
import argparse

from . import scraper
from . import builder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fantastat")

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # Reuse scraper parser
    scrape_parser = subparsers.add_parser(
        "scrape",
        parents=[scraper.build_arg_parser()],
        add_help=False,
        help="Scrape Fantacalcio data",
    )
    scrape_parser.set_defaults(func=scraper.main)

    builddb_parser = subparsers.add_parser(
        "builddb",
        parents=[builder.build_arg_parser()],
        add_help=False,
    )
    builddb_parser.set_defaults(func=builder.main)

    return parser


def main(argv: list[str] | None=sys.argv[1:]) -> int:
    parser = build_parser()

    args = parser.parse_args(argv)

    return args.func(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())