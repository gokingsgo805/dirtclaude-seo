#!/usr/bin/env python3
"""Audit a URL or an HTML file for SEO and answer-engine readiness.

Examples:
  python3 python/claimline/audit.py https://dirtclaude.ai --brand dirtClaude
  python3 python/claimline/audit.py --html page.html --brand dirtClaude
  python3 python/claimline/audit.py --html page.html --format md --fail-under 70
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from libchecks import score, to_markdown
from libextract import extract
from libfetch import FetchError, fetch_page, probe


def _looks_html(body: str, ctype: str) -> bool:
    if any(token in (ctype or "").lower() for token in ("html", "xml", "text/plain")):
        return True
    head = body[:800].lower()
    return any(mark in head for mark in ("<!doctype", "<html", "<head", "<body"))


def audit_html(html: str, brand: str, label: str, page_url: str | None = None) -> dict:
    signals = extract(html, page_url)
    return score(signals, brand=brand, label=label, source="html", final_url=page_url)


def audit_url(url: str, brand: str) -> dict:
    status, final, body, ctype = fetch_page(url)
    if not _looks_html(body, ctype):
        raise FetchError(f"Page returned {status} and it is not HTML." if status >= 400 else "That URL did not return HTML.")
    from urllib.parse import urlparse

    origin = f"{urlparse(final).scheme}://{urlparse(final).netloc}"
    robots_status, robots_body = probe(origin + "/robots.txt")
    llms_status, llms_body = probe(origin + "/llms.txt")
    sitemap_status, _sitemap = probe(origin + "/sitemap.xml")
    site = {
        "robotsStatus": robots_status,
        "robotsTxt": robots_body if robots_status == 200 else None,
        "llmsStatus": llms_status,
        "llmsBody": llms_body,
        "sitemapStatus": sitemap_status,
    }
    signals = extract(body, final)
    return score(signals, brand=brand, label=final, source="url", http_status=status, final_url=final, site=site)


def render(report: dict, fmt: str, verbose: bool) -> str:
    if fmt == "json":
        return json.dumps(report, indent=2)
    if fmt == "md":
        return to_markdown(report)
    scores = report["scores"]
    lines = [
        "Claimline audit",
        report.get("label") or "",
        f"Overall {scores['overall']}    SEO {scores['seo']}    AEO {scores['aeo']}",
        "",
    ]
    for severity in ("fail", "warn", "pass"):
        rows = [f for f in report["findings"] if f["severity"] == severity]
        if severity == "pass" and not verbose:
            if rows:
                lines.append(f"PASS  {len(rows)} checks. Use --verbose to list them.")
            continue
        if not rows:
            continue
        lines.append(severity.upper())
        for row in rows:
            lines.append(f"  [{row['pillar']}] {row['title']}")
            lines.append(f"        {row['detail']}")
            lines.append(f"        Fix: {row['fix']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Audit a page for SEO and answer-engine citation.")
    parser.add_argument("url", nargs="?", help="http(s) URL to fetch")
    parser.add_argument("--html", help="Audit a local HTML file instead of a URL")
    parser.add_argument("--brand", default="", help="Brand that should appear in the title and opening")
    parser.add_argument("--format", choices=("text", "json", "md"), default="text")
    parser.add_argument("--verbose", action="store_true", help="List passing checks in text output")
    parser.add_argument("--fail-under", type=int, default=None, help="Exit 1 when overall score is below this")
    args = parser.parse_args(argv)
    try:
        if args.html:
            html = Path(args.html).read_text(encoding="utf-8")
            report = audit_html(html, args.brand, args.html)
        elif args.url:
            report = audit_url(args.url, args.brand)
        else:
            parser.error("Pass a URL or --html file")
            return 2
    except (FetchError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(render(report, args.format, args.verbose))
    if args.fail_under is not None and report["scores"]["overall"] < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
