#!/usr/bin/env python3
"""Build an answer-first brief from a question and a draft. No model calls.

  python3 python/claimline/brief.py --question "What does dirtClaude show for a BLM claim?" \\
      --brand dirtClaude --draft-file notes.txt --path /guides/check-blm-claim
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from libbrief import build_brief


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Extract an AEO brief from a draft.")
    parser.add_argument("--question", required=True)
    parser.add_argument("--brand", default="")
    parser.add_argument("--draft-file", help="Text file. Omit to read stdin.")
    parser.add_argument("--path", default="/", help="Path used in the llms.txt line")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    if args.draft_file:
        draft = Path(args.draft_file).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        draft = sys.stdin.read()
    else:
        draft = ""
    brief = build_brief(args.question, args.brand, draft, args.path)
    if args.format == "json":
        print(json.dumps(brief, indent=2))
        return 0
    print(brief["title"])
    print(brief["description"])
    print()
    print(brief["answer"])
    print()
    for line in brief["outline"]:
        print(f"- {line}")
    print()
    for faq in brief["faqs"]:
        mark = "sourced" if faq["sourced"] else "needs a fact"
        print(f"Q: {faq['q']} ({mark})")
        print(f"A: {faq['a']}")
        print()
    if brief["jsonLd"]:
        print(brief["jsonLd"])
    print(brief["llmsLine"])
    for note in brief["notes"]:
        print(f"note: {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
