from __future__ import annotations

import argparse
import json
from pathlib import Path

from web.services.lineup_parser import LineupParser


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_html")
    parser.add_argument("output_json")
    parser.add_argument("--season", type=int, default=2027)
    args = parser.parse_args()

    payload = LineupParser().parse_file(args.input_html, season=args.season)
    Path(args.output_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
