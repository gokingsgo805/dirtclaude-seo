import json
import math
import re

from libtext import clean, clip, tokens, word_count


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", clean(text))
    return [p.strip() for p in parts if word_count(p) >= 6]


def _overlap(sentence: str, keys: set[str]) -> float:
    toks = tokens(sentence)
    if not toks or not keys:
        return 0
    hit = sum(1 for t in toks if t in keys)
    return hit / math.sqrt(len(toks))


def build_brief(question: str, brand: str = "", draft: str = "", path: str = "/") -> dict:
    question = clean(question).rstrip("?").strip()
    brand = clean(brand)
    path = (path or "/").strip() or "/"
    notes: list[str] = []
    if not question:
        return {
            "title": "",
            "description": "",
            "answer": "",
            "outline": [],
            "faqs": [],
            "jsonLd": "",
            "llmsLine": "",
            "notes": ["Enter the question a prospector would actually type."],
        }
    keys = set(tokens(f"{question} {brand}"))
    ranked = sorted(
        ({"s": s, "score": _overlap(s, keys)} for s in _sentences(draft)),
        key=lambda row: row["score"],
        reverse=True,
    )
    ranked = [row for row in ranked if row["score"] > 0]
    used: set[str] = set()
    picked: list[str] = []
    count = 0
    for row in ranked:
        if count >= 75:
            break
        picked.append(row["s"])
        used.add(row["s"])
        count += word_count(row["s"])
        if count >= 45:
            break
    text = clean(" ".join(picked))
    sourced = word_count(text) >= 20
    answer = text if sourced else (
        f'{brand or "This page"} should answer “{question}” in the first sentences. '
        "[State the direct answer in one sentence.] [Add one number, place, or date.] [Say who it is for and the limit.]"
    )
    if not sourced:
        notes.append("The draft did not contain enough overlapping sentences. Fill the brackets. Do not publish them.")
    base = question.rstrip("?")
    title = f"{base} | {brand}" if brand else base
    if len(title) > 60:
        title = clip(base, max(20, 60 - (len(brand) + 3 if brand else 0)))
    if brand and brand.lower() not in title.lower() and len(f"{title} | {brand}") <= 60:
        title = f"{title} | {brand}"
    if len(title) > 60:
        title = clip(title, 60)
    description = clip(answer, 155) if sourced else ""
    if not description:
        notes.append("Write the meta description after the answer is real. 110–160 characters.")
    outline = [
        f"Direct answer: {base}",
        f"How {brand} handles it" if brand else "How it works",
        "What you need in the field",
        "Limits, dates, and sources",
    ]
    all_sentences = _sentences(draft)
    unused = [s for s in all_sentences if s not in used]
    pool = unused + [s for s in all_sentences if s in used] if unused else all_sentences
    prompts = [
        base,
        f"How should {brand} answer this in the field?" if brand else "How should the page answer this in the field?",
        "Who is this for?",
        "What does this not cover?",
    ]
    faqs = []
    for i, q in enumerate(prompts):
        q = q if q.endswith("?") else q + "?"
        if i < len(pool) and word_count(pool[i]) >= 8:
            faqs.append({"q": q, "a": pool[i], "sourced": True})
        else:
            faqs.append({"q": q, "a": "Add a two-sentence answer with one concrete fact.", "sourced": False})
    schema_faqs = [f for f in faqs if f["sourced"]]
    json_ld = ""
    if schema_faqs:
        json_ld = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                    for f in schema_faqs
                ],
            },
            indent=2,
        )
    else:
        notes.append("FAQ schema is withheld until at least one answer comes from the draft.")
    summary = clip(answer, 140) if sourced else "[one-line summary with a fact]"
    return {
        "title": title,
        "description": description,
        "answer": answer,
        "outline": outline,
        "faqs": faqs,
        "jsonLd": json_ld,
        "llmsLine": f"- [{clip(base, 80)}]({path}): {summary}",
        "notes": notes,
    }
