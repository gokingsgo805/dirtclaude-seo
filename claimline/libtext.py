import re

FACT_RE = re.compile(
    r"\b(?:19|20)\d{2}\b|\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|\$?\d+\.\d+%?|\b\d{2,}%?"
)
STOP = set(
    "a an the of to for and or in on with without from by is are was were be this that it its as at your you we our their how what why when where who which can does do not into over per".split()
)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def words(text: str) -> list[str]:
    t = (text or "").strip()
    return t.split() if t else []


def word_count(text: str) -> int:
    return len(words(text))


def count_facts(text: str) -> int:
    return len(FACT_RE.findall(text or ""))


def clip(text: str, max_len: int) -> str:
    t = clean(text)
    if len(t) <= max_len:
        return t
    cut = t[: max_len - 1]
    trimmed = re.sub(r"\s+\S*$", "", cut)
    return (trimmed or cut) + "…"


def tokens(text: str) -> list[str]:
    raw = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower()).split()
    return [t for t in raw if len(t) > 2 and t not in STOP]
