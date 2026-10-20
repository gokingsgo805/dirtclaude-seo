#!/usr/bin/env python3
"""Turn a Q:/A: text file into FAQPage JSON-LD.

Blank line between pairs. Lines start with Q: or A:.

  python3 python/claimline/faq_schema.py python/claimline/fixtures/faqs.txt
"""

import argparse
import json
import sys
from pathlib import Path


def parse_pairs(text: str) -> list[tuple[str, str]]:
    pairs = []
    question = ""
    answer: list[str] = []
    mode = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.lower().startswith("q:"):
            if question and answer:
                pairs.append((question, " ".join(answer).strip()))
            question = line[2:].strip()
            answer = []
            mode = "q"
        elif line.lower().startswith("a:"):
            answer = [line[2:].strip()]
            mode = "a"
        elif not line:
            continue
        elif mode == "a":
            answer.append(line)
        elif mode == "q":
            question = (question + " " + line).strip()
    if question and answer:
        pairs.append((question, " ".join(answer).strip()))
    return pairs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build FAQPage JSON-LD from Q/A text.")
    parser.add_argument("path", nargs="?", help="Text file. Omit to read stdin.")
    args = parser.parse_args(argv)
    text = Path(args.path).read_text(encoding="utf-8") if args.path else sys.stdin.read()
    pairs = parse_pairs(text)
    if not pairs:
        print("error: no Q:/A: pairs found", file=sys.stderr)
        return 2
    doc = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in pairs
        ],
    }
    json.dump(doc, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
