#!/usr/bin/env python3
"""Run the Claimline checks against fixtures. No network."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from faq_schema import parse_pairs
from libbrief import build_brief
from libchecks import score
from libextract import extract
from libfetch import FetchError, validate_url
from librobots import parse_robots, path_allowed
from llms_txt import main as llms_main

ROOT = Path(__file__).resolve().parent


def check(cond: bool, message: str):
    if not cond:
        raise SystemExit(f"FAIL {message}")
    print(f"ok  {message}")


def main() -> int:
    strong = extract((ROOT / "fixtures" / "strong.html").read_text(encoding="utf-8"), "https://dirtclaude.ai/guides/check-blm-claim")
    weak = extract((ROOT / "fixtures" / "weak.html").read_text(encoding="utf-8"), None)
    strong_report = score(strong, brand="dirtClaude", label="strong", source="html")
    weak_report = score(weak, brand="dirtClaude", label="weak", source="html")
    print(json.dumps({"strong": strong_report["scores"], "weak": weak_report["scores"]}))
    check(strong_report["scores"]["overall"] >= 75, f"strong overall {strong_report['scores']['overall']} >= 75")
    check(weak_report["scores"]["overall"] <= 50, f"weak overall {weak_report['scores']['overall']} <= 50")
    check(strong_report["scores"]["aeo"] > weak_report["scores"]["aeo"], "strong AEO beats weak AEO")
    check("FAQPage" in strong["jsonLdTypes"], "strong page extracts FAQPage")
    check(strong["h2Count"] >= 2, "strong page has H2s")

    groups = parse_robots("User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n")
    check(path_allowed(groups, "GPTBot") is False, "GPTBot block is honored")
    check(path_allowed(groups, "PerplexityBot") is True, "other bots fall through to *")
    groups = parse_robots("User-agent: *\nDisallow:\n")
    check(path_allowed(groups, "ClaudeBot") is True, "empty disallow does not block")

    blocked = {
        "robotsStatus": 200,
        "robotsTxt": "User-agent: GPTBot\nDisallow: /\nUser-agent: ClaudeBot\nDisallow: /\n",
        "llmsStatus": 404,
        "llmsBody": "",
        "sitemapStatus": 404,
    }
    site_report = score(strong, brand="dirtClaude", label="site", source="url", http_status=200, site=blocked)
    ids = {f["id"]: f["severity"] for f in site_report["findings"]}
    check(ids.get("ai-crawlers") == "fail", "two blocked bots fail ai-crawlers")
    check(ids.get("llms-txt") == "fail", "missing llms.txt fails")

    empty = build_brief("What does dirtClaude show for a BLM claim?", "dirtClaude", "")
    check("[" in empty["answer"], "thin draft stays a scaffold")
    check(empty["jsonLd"] == "", "schema withheld without sourced answers")
    rich = build_brief(
        "What does dirtClaude show for a BLM claim?",
        "dirtClaude",
        "dirtClaude shows the claim on a bare-earth LiDAR and roads basemap before a field day. "
        "Recorded claimant details come from the BLM layer. "
        "An active claim is not permission to dig. Confirm the serial with the BLM. "
        "The map is for prospectors who need the road into the site.",
        "/guides/check-blm-claim",
    )
    check("[" not in rich["answer"], "rich draft extracts an answer")
    check("FAQPage" in rich["jsonLd"], "rich draft emits FAQ schema")

    pairs = parse_pairs((ROOT / "fixtures" / "faqs.txt").read_text(encoding="utf-8"))
    check(len(pairs) == 2, "faq file parses two pairs")

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = llms_main([str(ROOT / "fixtures" / "pages.csv"), "--name", "dirtClaude"])
    text = buf.getvalue()
    check(code == 0 and "https://dirtclaude.ai/guides/check-blm-claim" in text, "llms.txt lists the guide")

    for bad in ("http://127.0.0.1/", "http://169.254.169.254/", "http://localhost/admin", "file:///etc/passwd"):
        try:
            validate_url(bad)
        except FetchError:
            check(True, f"blocked {bad}")
        else:
            check(False, f"blocked {bad}")

    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
