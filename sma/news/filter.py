from __future__ import annotations

import re
from typing import Any

DROP_PUBLISHERS = {
    "motley fool",
    "the motley fool",
    "seeking alpha",
    "investorplace",
    "zacks",
    "tipranks",
    "benzinga",
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


def _blob(item: dict[str, Any]) -> str:
    return f"{item.get('title') or ''} {item.get('summary') or ''} {item.get('publisher') or ''}"


def mentions_company(item: dict[str, Any], ticker: str, name: str | None = None) -> bool:
    text = _blob(item).lower()
    if ticker.lower() in text:
        return True
    skip = {"inc", "corp", "corporation", "company", "holdings", "the", "and", "class", "plc"}
    tokens = [tok for tok in re.findall(r"[a-z]{3,}", (name or "").lower()) if tok not in skip]
    return any(tok in text for tok in tokens[:3])


def classify_rule(item: dict[str, Any]) -> str:
    publisher = str(item.get("publisher") or "").lower()
    if any(pub in publisher for pub in DROP_PUBLISHERS):
        return "drop"
    text = _blob(item)
    drop_hit = any(rx.search(text) for rx in DROP_RE)
    keep_hit = any(rx.search(text) for rx in KEEP_RE)
    if drop_hit and not keep_hit:
        return "drop"
    if keep_hit and not drop_hit:
        return "keep"
    if keep_hit and drop_hit:
        return "maybe"
    return "maybe"


def filter_news(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets = {"keep": [], "drop": [], "maybe": []}
    seen: set[str] = set()
    for item in items:
        key = (item.get("ticker"), (item.get("title") or "").lower().strip())
        if key in seen:
            continue
        seen.add(key)
        label = classify_rule(item)
        tagged = {**item, "rule_label": label}
        buckets[label].append(tagged)
    return buckets
