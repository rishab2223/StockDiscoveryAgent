from __future__ import annotations

import re
from typing import Any

# Opinion / stock-picking outlets: dropped whatever the headline says.
DROP_PUBLISHERS = {
    "motley fool",
    "the motley fool",
    "seeking alpha",
    "investorplace",
    "zacks",
    "tipranks",
    "benzinga",
    "simply wall st",
    "trefis",
    "tikr",
    "24/7 wall st",
}

DROP_PATTERNS = [
    r"\bupgrade(d|s)?\b",
    r"\bdowngrade(d|s)?\b",
    r"\bprice target\b",
    r"\bpt\s*to\b",
    r"\banalysts?\b",
    r"\binitiates? coverage\b",
    r"\breiterates?\b",
    r"\boverweight\b",
    r"\bunderweight\b",
    r"\bequal[- ]weight\b",
    r"\bbuy rating\b",
    r"\bsell rating\b",
    r"\bstock to buy\b",
    r"\bstocks to (buy|sell|watch)\b",
    r"\bwhy i'm\b",
    r"\bhere's why\b",
    r"\bmy take\b",
    r"\bopinion\b",
    r"\bshould you (buy|sell)\b",
    r"\bwedbush\b",
    r"\bbarclays\b",
    r"\bzacks\b",
    r"\bpiper sandler\b",
    r"\bmorgan stanley\b",
    r"\bgoldman sachs\b",
    r"\bbofa\b",
    r"\bjp ?morgan\b",
    r"\bseeking alpha\b",
    r"\bhedge funds?\b",
    r"\bthese \d+ stocks\b",
    r"\bbest stocks\b",
    r"\bmarket today\b",
    r"\bstock market\b",
    r"\bfutures\b",
    r"\bwhat to expect from the market\b",
    r"\bonly answer i can think\b",
    r"\bwhy does it trade\b",
    r"\bif .+ is a top\b",
    r"\bthis is why\b",
]

KEEP_PATTERNS = [
    r"\bearnings\b",
    r"\bguidance\b",
    r"\brevenue\b",
    r"\boutlook\b",
    r"\bdividend\b",
    r"\bbuyback\b",
    r"\brepurchase\b",
    r"\bacquires?\b",
    r"\bacquisition\b",
    r"\bmerger\b",
    r"\bspin[- ]off\b",
    r"\blaunches?\b",
    r"\bproduct\b",
    r"\bpartnership\b",
    r"\bcontract\b",
    r"\bfda\b",
    r"\b8-k\b",
    r"\b10-q\b",
    r"\b10-k\b",
    r"\bsec filing\b",
    r"\bpress release\b",
    r"\bannounces?\b",
    r"\brecalls?\b",
    r"\blawsuit\b",
    r"\bsettlement\b",
    r"\binvestigation\b",
    r"\bceo\b",
    r"\bcfo\b",
    r"\bappoints?\b",
    r"\bresigns?\b",
    r"\bguidance cut\b",
    r"\bguidance raise\b",
]

DROP_RE = [re.compile(p, re.I) for p in DROP_PATTERNS]
KEEP_RE = [re.compile(p, re.I) for p in KEEP_PATTERNS]

# Generic words that appear in most company names and would match any story.
_NAME_STOPWORDS = {"inc", "corp", "corporation", "company", "holdings", "the", "and", "class", "plc", "group"}


def _blob(item: dict[str, Any]) -> str:
    return f"{item.get('title') or ''} {item.get('summary') or ''} {item.get('publisher') or ''}"


def _ticker_pattern(ticker: str) -> re.Pattern[str]:
    """Case-sensitive symbol match so ALL, CAT or F do not match ordinary words.
    One- and two-letter symbols must appear as a cashtag or in parentheses."""
    symbol = re.escape(ticker)
    if len(ticker) <= 2:
        return re.compile(rf"(\${symbol}\b|\({symbol}\))")
    return re.compile(rf"(?<![A-Za-z0-9]){symbol}(?![A-Za-z0-9])")


def mentions_company(item: dict[str, Any], ticker: str, name: str | None = None) -> bool:
    """Is the story about this company? Yahoo's relatedTickers decides when present;
    otherwise the symbol or a distinctive word of the company name must appear."""
    related = item.get("related_tickers")
    if related:
        return ticker.upper() in {str(r).upper() for r in related}
    text = _blob(item)
    if _ticker_pattern(ticker).search(text):
        return True
    tokens = [tok for tok in re.findall(r"[a-z]{3,}", (name or "").lower()) if tok not in _NAME_STOPWORDS]
    return any(re.search(rf"\b{re.escape(tok)}\b", text, re.I) for tok in tokens[:3])


def classify_rule(item: dict[str, Any]) -> str:
    publisher = str(item.get("publisher") or "").lower()
    if any(pub in publisher for pub in DROP_PUBLISHERS):
        return "drop"
    text = _blob(item)
    drop_hit = any(rx.search(text) for rx in DROP_RE)
    keep_hit = any(rx.search(text) for rx in KEEP_RE)
    if drop_hit == keep_hit:  # neither pattern set fired, or both did
        return "maybe"
    return "drop" if drop_hit else "keep"


def filter_news(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Dedupe by (ticker, title) and split into keep / drop / maybe."""
    buckets: dict[str, list[dict[str, Any]]] = {"keep": [], "drop": [], "maybe": []}
    seen: set[tuple[Any, str]] = set()
    for item in items:
        key = (item.get("ticker"), (item.get("title") or "").lower().strip())
        if key in seen:
            continue
        seen.add(key)
        label = classify_rule(item)
        buckets[label].append({**item, "rule_label": label})
    return buckets
