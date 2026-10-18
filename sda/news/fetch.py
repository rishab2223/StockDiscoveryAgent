from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import yfinance as yf

from sda import config


def _content(item: dict[str, Any]) -> dict[str, Any]:
    """Newer Yahoo payloads nest the story under `content`; the search API is flat."""
    content = item.get("content")
    return content if isinstance(content, dict) else {}


def _published_at(item: dict[str, Any]) -> datetime | None:
    content = _content(item)
    raw = (
        item.get("providerPublishTime")
        or item.get("provider_publish_time")
        or content.get("pubDate")
        or content.get("displayTime")
    )
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        ts = float(raw)
        if ts > 1e12:  # milliseconds
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _headline(item: dict[str, Any]) -> str:
    return str(item.get("title") or _content(item).get("title") or item.get("headline") or "").strip()


def _summary(item: dict[str, Any]) -> str:
    content = _content(item)
    return str(item.get("summary") or content.get("summary") or content.get("description") or "").strip()


def _url(item: dict[str, Any]) -> str:
    content = _content(item)
    click = content.get("clickThroughUrl") or {}
    canonical = content.get("canonicalUrl") or {}
    return str(item.get("link") or click.get("url") or canonical.get("url") or "")


def _publisher(item: dict[str, Any]) -> str:
    provider = _content(item).get("provider") or {}
    return str(item.get("publisher") or provider.get("displayName") or "Yahoo")


def normalize_item(item: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    """One flat record from either Yahoo news shape; None when there is no headline."""
    title = _headline(item)
    if not title:
        return None
    published = _published_at(item)
    return {
        "ticker": ticker,
        "title": title,
        "summary": _summary(item),
        "url": _url(item),
        "publisher": _publisher(item),
        "published_at": published.isoformat() if published else None,
    }


def _raw_news(ticker: str, count: int) -> list[Any]:
    # yfinance 1.x: Ticker.news comes back empty for most symbols; Search still works.
    try:
        found = yf.Search(ticker, news_count=count).news
        if found:
            return list(found)
    except Exception:
        pass
    try:
        return list(yf.Ticker(ticker).get_news(count=count) or [])
    except Exception:
        return []


def fetch_ticker_news(
    ticker: str,
    lookback_days: int | None = None,
    count: int | None = None,
) -> list[dict[str, Any]]:
    """Recent Yahoo headlines for one ticker, newest first, within the lookback window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days or config.NEWS_LOOKBACK_DAYS)
    docs: list[dict[str, Any]] = []
    for item in _raw_news(ticker, count or config.NEWS_COUNT):
        if not isinstance(item, dict):
            continue
        doc = normalize_item(item, ticker)
        if doc is None:
            continue
        if doc["published_at"] and datetime.fromisoformat(doc["published_at"]) < cutoff:
            continue
        docs.append(doc)
    return docs
