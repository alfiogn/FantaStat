from __future__ import annotations

import argparse
import sys

from . import builder
from . import fetcher
from . import scraper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fantastat")

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

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
        help="Build MongoDB database from cached data",
    )
    builddb_parser.set_defaults(func=builder.main)

    fetchinfo_parser = subparsers.add_parser(
        "fetchinfo",
        parents=[fetcher.build_arg_parser()],
        add_help=False,
        help="Fetch RSS player information and generate LLM dossiers",
    )
    fetchinfo_parser.set_defaults(func=fetcher.main)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    parser = build_parser()
    args = parser.parse_args(argv)

    return args.func(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())