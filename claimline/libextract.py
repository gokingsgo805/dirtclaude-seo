import json
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

from libtext import clean, count_facts, word_count

SOCIAL = {
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "youtube.com",
    "youtu.be",
    "linkedin.com",
    "pinterest.com",
    "reddit.com",
}
BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6"}
MONTH = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b[^\n]{0,16}\b(?:19|20)\d{2}\b",
    re.I,
)


def _host(href: str, page_url: str | None) -> str | None:
    try:
        base = page_url or "https://claimline.local"
        if "://" not in href and not href.startswith("/"):
            href = urlparse(base).scheme + "://" + urlparse(base).netloc + "/" + href if False else href
        joined = href if "://" in href else (base.rstrip("/") + "/" + href.lstrip("/")) if href.startswith("/") else href
        if "://" not in joined:
            return None
        host = urlparse(joined).hostname or ""
        return host.lower().removeprefix("www.") or None
    except Exception:
        return None


def _social(host: str | None) -> bool:
    if not host:
        return False
    return any(host == s or host.endswith("." + s) for s in SOCIAL)


class _Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = ""
        self.title = ""
        self.metas: list[dict] = []
        self.links: list[dict] = []
        self.images: list[str] = []
        self.anchors: list[tuple[str, str]] = []
        self.blocks: list[tuple[str, str]] = []
        self.json_raw: list[str] = []
        self.list_count = 0
        self.table_count = 0
        self.time_date = False
        self.author_link = False
        self._skip = 0
        self._mode = ""
        self._buf: list[str] = []
        self._tag = ""
        self._a_href = ""
        self._a_buf: list[str] = []
        self._in_a = False
        self._title = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        tag = tag.lower()
        if tag in ("script", "style", "noscript"):
            if tag == "script" and "ld+json" in a.get("type", "").lower():
                self._mode = "json"
                self._buf = []
            else:
                self._skip += 1
            return
        if self._skip or self._mode == "json":
            return
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "meta":
            self.metas.append(a)
        elif tag == "link":
            rel = a.get("rel", "").lower().split()
            if "canonical" in rel:
                self.links.append({"rel": "canonical", "href": a.get("href", "")})
            if "author" in rel:
                self.author_link = True
        elif tag == "img":
            self.images.append(a.get("alt", ""))
        elif tag in ("ul", "ol"):
            self.list_count += 1
        elif tag == "table":
            self.table_count += 1
        elif tag == "time" and a.get("datetime"):
            self.time_date = True
        elif tag == "title":
            self._title = True
            self._buf = []
        elif tag in BLOCK:
            self._mode = "block"
            self._tag = tag
            self._buf = []
        elif tag == "a":
            self._in_a = True
            self._a_href = a.get("href", "")
            self._a_buf = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("script", "style", "noscript"):
            if self._mode == "json" and tag == "script":
                self.json_raw.append("".join(self._buf))
                self._mode = ""
            elif self._skip:
                self._skip -= 1
            return
        if self._skip or self._mode == "json":
            return
        if tag == "title" and self._title:
            self.title = clean("".join(self._buf))
            self._title = False
        elif tag in BLOCK and self._mode == "block" and tag == self._tag:
            text = clean("".join(self._buf))
            if text:
                self.blocks.append((tag, text))
            self._mode = ""
        elif tag == "a" and self._in_a:
            self.anchors.append((self._a_href, clean("".join(self._a_buf))))
            self._in_a = False

    def handle_data(self, data):
        if self._mode == "json" or self._title or self._mode == "block":
            self._buf.append(data)
        if self._in_a and not self._skip and self._mode != "json":
            self._a_buf.append(data)


def _meta(metas: list[dict], name: str, attr: str = "name") -> str:
    want = name.lower()
    for m in metas:
        if m.get(attr, "").lower() == want:
            return m.get("content", "")
    return ""


def _types(node, out: list[str]):
    if isinstance(node, list):
        for item in node:
            _types(item, out)
        return
    if not isinstance(node, dict):
        return
    t = node.get("@type")
    if isinstance(t, str):
        out.append(t)
    elif isinstance(t, list):
        out.extend(x for x in t if isinstance(x, str))
    if "@graph" in node:
        _types(node["@graph"], out)


def extract(html: str, page_url: str | None) -> dict:
    parser = _Extract()
    parser.feed(html or "")
    types: list[str] = []
    errors = 0
    for raw in parser.json_raw:
        raw = raw.strip()
        if not raw:
            continue
        try:
            _types(json.loads(raw), types)
        except json.JSONDecodeError:
            errors += 1
    blob = "\n".join(parser.json_raw)
    title = parser.title
    description = clean(_meta(parser.metas, "description"))
    canonical = next((l["href"] for l in parser.links if l["rel"] == "canonical"), "")
    robots_meta = clean(_meta(parser.metas, "robots")).lower()
    viewport = any(m.get("name", "").lower() == "viewport" for m in parser.metas)
    og_title = bool(_meta(parser.metas, "og:title", "property") or _meta(parser.metas, "og:title"))
    og_desc = bool(_meta(parser.metas, "og:description", "property") or _meta(parser.metas, "og:description"))
    headings = [{"level": int(tag[1]), "text": text} for tag, text in parser.blocks if tag.startswith("h")]
    h1 = [h["text"] for h in headings if h["level"] == 1]
    paragraphs = [text for tag, text in parser.blocks if tag == "p"]
    list_items = [text for tag, text in parser.blocks if tag == "li"]
    h2_at = next((i for i, (tag, _) in enumerate(parser.blocks) if tag == "h2"), -1)
    intro_src = parser.blocks if h2_at < 0 else parser.blocks[:h2_at]
    intro = clean(" ".join(text for tag, text in intro_src if tag == "p"))
    section_words: list[int] = []
    bucket = 0
    seen = False
    for tag, text in parser.blocks:
        if tag == "h2":
            if seen:
                section_words.append(bucket)
            seen = True
            bucket = 0
            continue
        if seen and tag in ("p", "li"):
            bucket += word_count(text)
    if seen:
        section_words.append(bucket)
    body = clean(" ".join(text for _, text in parser.blocks))
    page_host = _host(page_url, None) if page_url else None
    links = []
    for href, text in parser.anchors:
        host = _host(href, page_url) if href else None
        absolute = href.lower().startswith("http://") or href.lower().startswith("https://")
        external = bool(host and absolute and (not page_host or host != page_host))
        links.append({"href": href, "text": text, "external": external, "social": _social(host)})
    author = bool(_meta(parser.metas, "author")) or parser.author_link or bool(re.search(r'"author"', blob, re.I)) or bool(re.search(r"\b(written by|author:)\b", body, re.I))
    meta_date = bool(
        _meta(parser.metas, "article:published_time", "property")
        or _meta(parser.metas, "article:modified_time", "property")
        or _meta(parser.metas, "date")
    )
    has_date = parser.time_date or meta_date or bool(re.search(r"date(modified|published)", blob, re.I)) or bool(MONTH.search(body)) or bool(re.search(r"\b(?:19|20)\d{2}\b", blob))
    return {
        "url": page_url,
        "title": title,
        "metaDescription": description,
        "canonical": canonical,
        "robotsMeta": robots_meta,
        "viewport": viewport,
        "lang": parser.lang,
        "h1": h1,
        "headings": headings,
        "paragraphs": paragraphs,
        "listItems": list_items,
        "intro": intro,
        "sectionWords": section_words,
        "h2Count": sum(1 for h in headings if h["level"] == 2),
        "wordCount": word_count(body),
        "bodyText": body,
        "images": [{"alt": clean(a)} for a in parser.images],
        "links": links,
        "jsonLdTypes": types,
        "jsonLdErrors": errors,
        "hasAuthor": author,
        "hasDate": has_date,
        "ogTitle": og_title,
        "ogDescription": og_desc,
        "listCount": parser.list_count,
        "tableCount": parser.table_count,
        "factHits": count_facts(body),
    }
