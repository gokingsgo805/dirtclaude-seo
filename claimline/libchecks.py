"""Page checks. Keep ids aligned with src/lib/audit/score.ts."""

import re

from librobots import bot_report
from libtext import word_count, words

PRIORITY = {
    "Organization",
    "WebSite",
    "WebPage",
    "Article",
    "BlogPosting",
    "NewsArticle",
    "FAQPage",
    "SoftwareApplication",
    "Dataset",
    "Place",
    "Product",
    "BreadcrumbList",
    "HowTo",
}
BAD_LINK = re.compile(r"^(click here|here|read more|learn more|link|this|more)$", re.I)
FLUFF = re.compile(
    r"^(welcome|hello|hi there|click here|we are glad|we're glad|thanks for visiting|this (website|site|page)\b)",
    re.I,
)
QUESTION = re.compile(r"^(how|what|why|when|where|who|which|can|does|do|is|are|should|will)\b", re.I)


def _f(id_, pillar, severity, weight, title, detail, fix):
    return {
        "id": id_,
        "pillar": pillar,
        "severity": severity,
        "weight": weight,
        "title": title,
        "detail": detail,
        "fix": fix,
    }


def _pillar(findings, pillar):
    rows = [f for f in findings if f["pillar"] == pillar]
    weight = sum(f["weight"] for f in rows)
    if not weight:
        return 0
    earned = 0
    for f in rows:
        unit = 1 if f["severity"] == "pass" else 0.5 if f["severity"] == "warn" else 0
        earned += f["weight"] * unit
    return round(earned / weight * 100)


def _q(text: str) -> bool:
    return "?" in text or bool(QUESTION.match(text))


def score(signals: dict, brand: str = "", label: str = "", source: str = "html", http_status=None, final_url=None, site=None) -> dict:
    brand = (brand or "").strip()
    s = signals
    findings = []

    if http_status is not None and http_status >= 400:
        findings.append(_f("http-status", "seo", "fail", 12, f"Page returned {http_status}", "Answer engines and Google both drop pages that do not return a successful document.", "Fix the URL, the redirect, or the server error before tuning copy."))

    title = s.get("title") or ""
    title_len = len(title)
    if not title:
        findings.append(_f("title-length", "seo", "fail", 12, "Missing title", "The title is the line most often quoted in search and in AI citations.", "Write a title that states the answer and the brand, about 50–60 characters."))
    elif title_len < 15 or title_len > 70:
        findings.append(_f("title-length", "seo", "fail", 12, "Title length is off", f"The title is {title_len} characters. Very short titles lack a query. Very long titles get cut.", "Aim for 30–60 characters, with the answer before the brand."))
    elif title_len < 30 or title_len > 60:
        findings.append(_f("title-length", "seo", "warn", 12, "Title length is close", f"The title is {title_len} characters. 30–60 is the band that stays intact in search snippets.", "Trim or expand so the useful words land inside 60 characters."))
    else:
        findings.append(_f("title-length", "seo", "pass", 12, "Title length is in range", f"“{title}” is {title_len} characters.", "Keep the answer in the first words when you rewrite."))

    desc = s.get("metaDescription") or ""
    desc_len = len(desc)
    if not desc:
        findings.append(_f("meta-description", "seo", "fail", 10, "Missing meta description", "Without a description, search snippets and some AI previews invent one from random page text.", "Write 110–160 characters that answer the query in one breath."))
    elif desc_len < 70 or desc_len > 180:
        findings.append(_f("meta-description", "seo", "warn", 10, "Meta description length is off", f"The description is {desc_len} characters.", "Rewrite it to 110–160 characters, leading with the answer."))
    elif desc_len < 110 or desc_len > 165:
        findings.append(_f("meta-description", "seo", "warn", 10, "Meta description is close", f"The description is {desc_len} characters. 110–160 reads as a complete snippet.", "Add or cut a short clause so it lands in that band."))
    else:
        findings.append(_f("meta-description", "seo", "pass", 10, "Meta description is in range", f"{desc_len} characters.", "Keep it aligned with the first paragraph so citations stay consistent."))

    h1 = s.get("h1") or []
    if not h1:
        findings.append(_f("h1", "seo", "fail", 10, "No H1", "The page has no H1, so the topic is not explicit.", "Add one H1 that matches the title’s promise."))
    elif len(h1) > 1:
        findings.append(_f("h1", "seo", "warn", 10, "More than one H1", f"Found {len(h1)} H1s: {' · '.join(h1[:3])}", "Keep a single H1. Demote the rest to H2."))
    else:
        findings.append(_f("h1", "seo", "pass", 10, "Single H1", h1[0], "Keep this H1 aligned with the title."))

    headings = s.get("headings") or []
    if len(headings) >= 2:
        skip = False
        prev = headings[0]["level"]
        for h in headings[1:]:
            if h["level"] > prev + 1:
                skip = True
            prev = h["level"]
        findings.append(
            _f("heading-order", "seo", "fail", 6, "Heading levels skip", "A heading jumps more than one level. Extractors use the outline as a map.", "Step H2 under H1, H3 under H2. Do not jump from H1 to H3.")
            if skip
            else _f("heading-order", "seo", "pass", 6, "Heading order is intact", "Levels step by one.", "Keep new sections on that ladder.")
        )

    findings.append(
        _f("html-lang", "seo", "pass", 4, "Language is set", f'html lang="{s.get("lang")}".', "Keep lang on the document element.")
        if s.get("lang")
        else _f("html-lang", "seo", "warn", 4, "Language is missing", "html has no lang attribute.", 'Add lang="en" (or the page language) on the html element.')
    )
    findings.append(
        _f("viewport", "seo", "pass", 4, "Viewport is set", "The page declares a viewport.", "Leave the viewport meta in the head.")
        if s.get("viewport")
        else _f("viewport", "seo", "fail", 4, "Viewport is missing", "Phones will not scale the page correctly.", 'Add <meta name="viewport" content="width=device-width, initial-scale=1">.')
    )
    findings.append(
        _f("canonical", "seo", "pass", 6, "Canonical is set", s.get("canonical") or "", "Point canonical at the URL you want cited.")
        if s.get("canonical")
        else _f("canonical", "seo", "warn", 6, "Canonical is missing", "Duplicate URLs can split the citation.", "Add a link rel=canonical to the preferred URL.")
    )

    robots_meta = s.get("robotsMeta") or ""
    if "noindex" in robots_meta:
        findings.append(_f("indexable", "seo", "fail", 8, "Page is noindex", f'robots meta is “{robots_meta}”.', "Remove noindex on any page you want cited. Keep it only on drafts and utility URLs."))
    elif "nosnippet" in robots_meta:
        findings.append(_f("indexable", "seo", "warn", 8, "Snippets are restricted", f'robots meta is “{robots_meta}”.', "Drop nosnippet if you want the answer quoted."))
    else:
        findings.append(_f("indexable", "seo", "pass", 8, "Page is indexable", f"robots: {robots_meta}" if robots_meta else "No noindex.", "Do not add noindex to public guides."))

    images = s.get("images") or []
    if images:
        with_alt = sum(1 for img in images if img.get("alt"))
        ratio = with_alt / len(images)
        severity = "pass" if ratio >= 0.9 else "warn" if ratio >= 0.5 else "fail"
        findings.append(_f("image-alt", "seo", severity, 6, "Image alts cover the page" if severity == "pass" else "Image alt text is thin", f"{with_alt} of {len(images)} images have alt text.", "Describe the image in the alt, or mark decorative images with an empty alt."))

    if s.get("ogTitle") and s.get("ogDescription"):
        findings.append(_f("open-graph", "seo", "pass", 6, "Open Graph is set", "og:title and og:description are present.", "Keep them in sync with the title and description."))
    else:
        findings.append(_f("open-graph", "seo", "warn", 6, "Open Graph is incomplete", f"og:title {'yes' if s.get('ogTitle') else 'no'}, og:description {'yes' if s.get('ogDescription') else 'no'}.", "Add both og:title and og:description so shares and some AI previews have a stable blurb."))

    wc = s.get("wordCount") or 0
    if wc < 80:
        findings.append(_f("word-count", "seo", "fail", 8, "Thin copy", f"{wc} words of visible text. That is not enough to answer a question.", "Write the direct answer, the steps, and the limit. Most citable guides clear 250 words."))
    elif wc < 250:
        findings.append(_f("word-count", "seo", "warn", 8, "Short copy", f"{wc} words. Usable, but thin next to a full guide.", "Add one section with a concrete fact, a step list, and a source."))
    else:
        findings.append(_f("word-count", "seo", "pass", 8, "Enough copy to cite", f"{wc} words.", "Keep new sections short rather than adding filler."))

    real_links = [l for l in (s.get("links") or []) if l.get("href") and not str(l["href"]).startswith("#")]
    if real_links:
        bad = [l for l in real_links if BAD_LINK.match(l.get("text") or "")]
        severity = "pass" if not bad else "fail" if len(bad) * 2 >= len(real_links) else "warn"
        findings.append(_f("link-text", "seo", severity, 4, "Link text is descriptive" if severity == "pass" else "Link text is vague", f'{len(bad)} link(s) say “{bad[0]["text"]}”.' if bad else f"{len(real_links)} links use visible text.", "Replace “click here” and “read more” with the name of the destination."))

    types = s.get("jsonLdTypes") or []
    errors = s.get("jsonLdErrors") or 0
    if not types:
        findings.append(_f("json-ld", "aeo", "fail", 10, "No JSON-LD", f"{errors} JSON-LD block(s) failed to parse." if errors else "The page has no structured data.", "Add Organization plus FAQPage or Article JSON-LD that matches the visible copy."))
    else:
        findings.append(_f("json-ld", "aeo", "warn" if errors else "pass", 10, "JSON-LD parsed with errors" if errors else "JSON-LD is present", f"Types: {', '.join(types)}{f'. {errors} block(s) failed.' if errors else '.'}", "Keep the JSON valid and matching the words on the page."))
        useful = [t for t in types if t in PRIORITY]
        findings.append(
            _f("schema-types", "aeo", "pass", 8, "Schema types are useful", ", ".join(useful), "Add FAQPage when the page answers more than one question.")
            if useful
            else _f("schema-types", "aeo", "warn", 8, "Schema types are generic", ", ".join(types), "Prefer Organization, Article, FAQPage, Dataset, or BreadcrumbList.")
        )

    q_heads = [h for h in headings if _q(h["text"])]
    has_faq = "FAQPage" in types
    if has_faq or len(q_heads) >= 2:
        findings.append(_f("faq-surface", "aeo", "pass", 8, "Questions are easy to lift", "FAQPage schema is present." if has_faq else f"{len(q_heads)} question headings.", "Keep each answer directly under its question, in 40–80 words."))
    elif len(q_heads) == 1 or wc <= 200:
        findings.append(_f("faq-surface", "aeo", "warn", 8, "Few explicit questions", "One question heading." if q_heads else "No question headings or FAQ schema.", "Add two or more H2 questions with short answers, and mirror them in FAQPage schema."))
    else:
        findings.append(_f("faq-surface", "aeo", "fail", 8, "No question surface", "Answer engines look for a question and a tight answer.", "Add an FAQ section: question H2s plus FAQPage JSON-LD copied from the visible text."))

    intro = s.get("intro") or ""
    intro_words = word_count(intro)
    if intro_words < 20 or FLUFF.match(intro):
        detail = "The opening has fewer than 20 words before the next section." if intro_words < 20 else f"The opening starts with filler: “{' '.join(words(intro)[:8])}”."
        findings.append(_f("answer-first", "aeo", "fail", 10, "The answer is not first", detail, "Open with 40–80 words that answer the query. Save the welcome line."))
    elif intro_words > 160:
        findings.append(_f("answer-first", "aeo", "warn", 10, "The opening is long", f"{intro_words} words before the first H2. Citations usually lift the first short paragraph.", "Split the opening so the first paragraph is the answer and the rest is context."))
    elif intro_words >= 35:
        findings.append(_f("answer-first", "aeo", "pass", 10, "Answer leads the page", f"{intro_words} words before the first H2.", "Keep that paragraph factual and self-contained."))
    else:
        findings.append(_f("answer-first", "aeo", "warn", 10, "Opening is a bit short", f"{intro_words} words before the first H2.", "Add one sentence with a place, number, or limit so the answer stands alone."))

    if wc >= 40:
        density = (s.get("factHits") or 0) / (wc / 100)
        shown = f"{density:.1f}"
        hits = s.get("factHits") or 0
        if density >= 0.8:
            findings.append(_f("fact-density", "aeo", "pass", 8, "Facts are dense enough", f"{hits} numbers or years ({shown} per 100 words).", "Keep dates and counts next to the claim they support."))
        elif density >= 0.25:
            findings.append(_f("fact-density", "aeo", "warn", 8, "Few hard facts", f"{hits} numbers or years ({shown} per 100 words).", "Add a year, a count, a distance, or a named source in the opening sections."))
        else:
            findings.append(_f("fact-density", "aeo", "fail", 8, "Almost no facts", f"{hits} numbers or years in {wc} words.", "Replace adjectives with a date, a count, or a named primary source."))

    if wc >= 200:
        h2_count = s.get("h2Count") or 0
        section_words = s.get("sectionWords") or []
        if h2_count < 2:
            findings.append(_f("chunking", "aeo", "fail", 6, "Page is one block", "Fewer than two H2 sections.", "Break the page into H2 sections a model can quote one at a time."))
        elif any(n > 320 for n in section_words):
            findings.append(_f("chunking", "aeo", "warn", 6, "A section is long", f"Longest H2 section is {max(section_words)} words.", "Keep each H2 section under about 280 words. Split steps into a list."))
        else:
            findings.append(_f("chunking", "aeo", "pass", 6, "Sections are quotable", f"{h2_count} H2 sections, none oversized.", "Stay with short sections when you add topics."))

    if brand:
        needle = brand.lower()
        in_title = needle in title.lower()
        in_h1 = any(needle in h.lower() for h in h1)
        in_open = needle in (s.get("bodyText") or "")[:400].lower()
        if in_title and (in_h1 or in_open):
            findings.append(_f("entity", "aeo", "pass", 8, "Brand is in the opening", f"{brand} appears in the title and the opening.", "Use the same spelling everywhere you want the entity resolved."))
        elif in_title or in_h1 or in_open:
            findings.append(_f("entity", "aeo", "warn", 8, "Brand is easy to miss", f"{brand} is not in both the title and the opening.", "Put the brand in the title and in the first paragraph or the H1."))
        else:
            findings.append(_f("entity", "aeo", "fail", 8, "Brand is absent", f"{brand} does not appear in the title or the opening.", "Name the brand in the title and the first paragraph so citations attach to the right entity."))

    findings.append(
        _f("attribution", "aeo", "pass", 6, "Attribution is present", "An author, byline, or Organization author is detectable.", "Keep a visible byline that matches the schema.")
        if s.get("hasAuthor")
        else _f("attribution", "aeo", "warn", 6, "No attribution", "No author meta, byline, or schema author.", "Add a visible byline and an Organization or Person author in JSON-LD.")
    )
    findings.append(
        _f("freshness", "aeo", "pass", 6, "A date is detectable", "The page exposes a year, a time element, or a schema date.", "Show the updated date in the copy, not only in schema.")
        if s.get("hasDate")
        else _f("freshness", "aeo", "warn", 6, "No date", "Nothing looks like a published or updated date.", "Add “Updated 12 October 2026” in the copy and dateModified in the Article schema.")
    )

    extractable = (s.get("listCount") or 0) + (s.get("tableCount") or 0) > 0 or len(s.get("listItems") or []) >= 3
    if extractable:
        findings.append(_f("extractable", "aeo", "pass", 6, "Lists or tables are present", "Structured blocks are easier to quote than prose.", "Keep list items as full statements, not fragments."))
    elif wc > 200:
        findings.append(_f("extractable", "aeo", "fail", 6, "No list or table", "The page is prose only.", "Pull steps, requirements, or comparisons into a list."))
    else:
        findings.append(_f("extractable", "aeo", "warn", 6, "No list or table", "Nothing is marked as a list or table.", "Add a short list of steps or constraints."))

    citations = [l for l in (s.get("links") or []) if l.get("external") and not l.get("social")]
    social_only = any(l.get("external") and l.get("social") for l in (s.get("links") or [])) and not citations
    if citations:
        shown = " · ".join((l.get("text") or l.get("href") or "") for l in citations[:2])
        findings.append(_f("citations", "aeo", "pass", 5, "Primary source linked", shown, "Keep outbound links on the claim they support."))
    else:
        findings.append(_f("citations", "aeo", "warn", 5, "Only social links leave the site" if social_only else "No outbound source", "Answer engines prefer pages that point at a primary record.", "Link the BLM, USGS, or other primary page that backs the claim."))

    para_words = [word_count(p) for p in (s.get("paragraphs") or [])]
    if any(40 <= n <= 90 for n in para_words):
        findings.append(_f("quotable", "aeo", "pass", 5, "A paragraph is quotable", "At least one paragraph is 40–90 words.", "That is the length models lift cleanly."))
    elif any(25 <= n <= 110 for n in para_words):
        findings.append(_f("quotable", "aeo", "warn", 5, "Paragraphs are close", "No paragraph sits in the 40–90 word band.", "Rewrite the answer paragraph into that band."))
    else:
        findings.append(_f("quotable", "aeo", "fail", 5, "No quotable paragraph", "Paragraphs are too short or too long to lift.", "Write one 40–90 word paragraph that answers the query alone."))

    site_report = None
    if site is not None:
        bots = bot_report(site.get("robotsTxt"), site.get("robotsStatus"))
        site_report = {
            "robotsStatus": site.get("robotsStatus"),
            "llmsStatus": site.get("llmsStatus"),
            "sitemapStatus": site.get("sitemapStatus"),
            "bots": bots,
        }
        blocked = [b for b in bots if b["status"] == "block"]
        if site.get("robotsStatus") is None:
            findings.append(_f("ai-crawlers", "aeo", "warn", 10, "robots.txt could not be fetched", "The host did not return a readable robots.txt.", "Confirm the file is public at /robots.txt."))
        elif site.get("robotsStatus") >= 400:
            findings.append(_f("ai-crawlers", "aeo", "pass", 10, "Answer bots are allowed", "No robots.txt. Crawlers are allowed by default.", "Publish a robots.txt only if you need to block a path. Do not block GPTBot, OAI-SearchBot, Google-Extended, PerplexityBot, or ClaudeBot on public pages."))
        elif len(blocked) >= 2:
            findings.append(_f("ai-crawlers", "aeo", "fail", 10, "Answer bots are blocked", f"{', '.join(b['name'] for b in blocked)} cannot fetch /.", "Allow those user agents in robots.txt if you want this site cited."))
        elif len(blocked) == 1:
            findings.append(_f("ai-crawlers", "aeo", "warn", 10, "One answer bot is blocked", f"{blocked[0]['name']} is disallowed for /.", "Allow it unless you have a specific reason to stay out of that engine."))
        else:
            findings.append(_f("ai-crawlers", "aeo", "pass", 10, "Answer bots are allowed", "GPTBot, Google-Extended, PerplexityBot, ClaudeBot, and Bingbot can fetch /.", "Keep public guides allowed."))

        llms = (site.get("llmsBody") or "").strip()
        llms_html = llms.lower().startswith("<!doctype") or llms.lower().startswith("<html")
        status = site.get("llmsStatus")
        if status is None:
            findings.append(_f("llms-txt", "aeo", "warn", 8, "llms.txt could not be fetched", "The request failed.", "Serve a text file at /llms.txt."))
        elif status in (404, 410):
            findings.append(_f("llms-txt", "aeo", "fail", 8, "llms.txt is missing", "Answer engines that look for /llms.txt get nothing.", "Publish a plain-text index of your canonical URLs with a one-line summary each."))
        elif status == 200 and llms_html:
            findings.append(_f("llms-txt", "aeo", "fail", 8, "llms.txt is HTML", "The URL returned a page, not a text index.", "Return text/plain with a markdown list of URLs."))
        elif status == 200 and len(llms) > 20:
            findings.append(_f("llms-txt", "aeo", "pass", 8, "llms.txt is live", f"{len(llms)} characters at /llms.txt.", "Keep each line as a title, URL, and one-sentence summary."))
        elif status == 200:
            findings.append(_f("llms-txt", "aeo", "warn", 8, "llms.txt is nearly empty", "The file is too short to be an index.", "List the canonical guides with one-line summaries."))
        else:
            findings.append(_f("llms-txt", "aeo", "warn", 8, "llms.txt returned an error", f"Status {status}.", "Serve the file with status 200 and text/plain."))

        sm = site.get("sitemapStatus")
        if sm == 200:
            findings.append(_f("sitemap", "seo", "pass", 3, "Sitemap responds", "/sitemap.xml returned 200.", "Keep new guides in the sitemap."))
        elif sm is None:
            findings.append(_f("sitemap", "seo", "warn", 3, "Sitemap could not be fetched", "The request failed.", "Publish /sitemap.xml and reference it in robots.txt."))
        else:
            findings.append(_f("sitemap", "seo", "warn", 3, "Sitemap is missing", f"/sitemap.xml returned {sm}.", "Publish an XML sitemap of canonical URLs."))

    seo = _pillar(findings, "seo")
    aeo = _pillar(findings, "aeo")
    overall = round(seo * 0.42 + aeo * 0.58)
    return {
        "label": label,
        "source": source,
        "httpStatus": http_status,
        "finalUrl": final_url or s.get("url"),
        "scores": {"overall": overall, "seo": seo, "aeo": aeo},
        "findings": findings,
        "extract": {
            "title": title,
            "description": desc,
            "h1": h1,
            "wordCount": wc,
            "jsonLdTypes": types,
        },
        "site": site_report,
    }


def to_markdown(report: dict) -> str:
    lines = ["# Claimline audit", "", report.get("label") or ""]
    if report.get("finalUrl"):
        lines.append(report["finalUrl"])
    scores = report["scores"]
    lines += ["", f"Overall {scores['overall']} · SEO {scores['seo']} · AEO {scores['aeo']}", ""]
    for severity in ("fail", "warn", "pass"):
        rows = [f for f in report["findings"] if f["severity"] == severity]
        if not rows:
            continue
        lines.append(f"## {severity}")
        lines.append("")
        for row in rows:
            lines.append(f"- **{row['title']}** ({row['pillar']}) — {row['detail']}")
            lines.append(f"  Fix: {row['fix']}")
        lines.append("")
    return "\n".join(lines)
