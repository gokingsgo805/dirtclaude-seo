#!/usr/bin/env python3
"""Write an llms.txt index from a CSV of title,url,summary.

  python3 python/claimline/llms_txt.py python/claimline/fixtures/pages.csv \\
      --name dirtClaude --about "Field maps for claims, mines, and mineral occurrences."
"""

import argparse
import csv
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build an llms.txt from a CSV.")
    parser.add_argument("csv_path", help="CSV with title,url,summary columns")
    parser.add_argument("--name", default="dirtClaude")
    parser.add_argument("--about", default="Field maps for mining claims, historical mines, and mineral occurrences.")
    parser.add_argument("-o", "--out", help="Write to this file instead of stdout")
    args = parser.parse_args(argv)
    path = Path(args.csv_path)
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    lines = [f"# {args.name}", f"> {args.about}", "", "## Pages"]
    for row in rows:
        title = (row.get("title") or "").strip()
        url = (row.get("url") or "").strip()
        summary = (row.get("summary") or "").strip()
        if not title or not url:
            continue
        lines.append(f"- [{title}]({url}): {summary}")
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
