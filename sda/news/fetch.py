from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import yfinance as yf

from sda.config import NEWS_LOOKBACK_DAYS


def _published_at(item: dict[str, Any]) -> datetime | None:
    content = item.get("content") if isinstance(item.get("content"), dict) else item
    raw = (
        item.get("providerPublishTime")
        or item.get("provider_publish_time")
        or (content or {}).get("pubDate")
        or (content or {}).get("displayTime")
    )
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        ts = float(raw)
        if ts > 1e12:
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    text = str(raw).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _headline(item: dict[str, Any]) -> str:
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    return str(
        item.get("title")
        or content.get("title")
        or item.get("headline")
        or ""
    ).strip()


def _summary(item: dict[str, Any]) -> str:
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    return str(
        item.get("summary")
        or content.get("summary")
        or content.get("description")
        or ""
    ).strip()


def _url(item: dict[str, Any]) -> str:
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    click = content.get("clickThroughUrl") or {}
    canonical = content.get("canonicalUrl") or {}
    link = item.get("link") or click.get("url") or canonical.get("url") or ""
    return str(link)


def _publisher(item: dict[str, Any]) -> str:
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    provider = content.get("provider") or {}
    return str(item.get("publisher") or provider.get("displayName") or "Yahoo")


def fetch_ticker_news(ticker: str, lookback_days: int = NEWS_LOOKBACK_DAYS) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        raw = []

    docs: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        published = _published_at(item)
        if published is not None and published < cutoff:
            continue
        title = _headline(item)
        if not title:
            continue
        docs.append(
            {
                "ticker": ticker,
                "title": title,
                "summary": _summary(item),
                "url": _url(item),
                "publisher": _publisher(item),
                "published_at": published.isoformat() if published else None,
            }
        )
    return docs
