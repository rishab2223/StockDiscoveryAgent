from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sda.news import fetch as fetch_mod
from sda.news.fetch import _published_at, fetch_ticker_news, normalize_item


def test_published_at_accepts_epoch_seconds_millis_and_iso():
    assert _published_at({"providerPublishTime": 1_700_000_000}) == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
    assert _published_at({"providerPublishTime": 1_700_000_000_000}) == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
    assert _published_at({"content": {"pubDate": "2026-10-01T12:00:00Z"}}) == datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    assert _published_at({"content": {"displayTime": "2026-10-01T12:00:00"}}).tzinfo is timezone.utc
    assert _published_at({"content": {"pubDate": "not a date"}}) is None
    assert _published_at({}) is None


def test_normalize_flat_search_shape():
    item = {
        "title": "Acme wins contract",
        "publisher": "Reuters",
        "link": "https://x/y",
        "providerPublishTime": 1_700_000_000,
        "relatedTickers": ["acme", "OTHER"],
    }
    doc = normalize_item(item, "ACME")
    assert doc["ticker"] == "ACME" and doc["title"] == "Acme wins contract"
    assert doc["url"] == "https://x/y" and doc["publisher"] == "Reuters"
    assert doc["published_at"] == "2023-11-14T22:13:20+00:00"
    assert doc["related_tickers"] == ["ACME", "OTHER"]
    assert doc["summary"] == ""


def test_normalize_nested_content_shape():
    item = {
        "content": {
            "title": "  Nested headline ",
            "summary": "Body",
            "pubDate": "2026-10-01T12:00:00Z",
            "provider": {"displayName": "AP"},
            "canonicalUrl": {"url": "https://canon"},
        }
    }
    doc = normalize_item(item, "X")
    assert doc["title"] == "Nested headline" and doc["summary"] == "Body"
    assert doc["publisher"] == "AP" and doc["url"] == "https://canon"
    assert normalize_item({"content": {"summary": "no title"}}, "X") is None


def test_fetch_applies_lookback_and_skips_junk(monkeypatch):
    now = datetime.now(timezone.utc)
    raw = [
        {"title": "fresh", "providerPublishTime": (now - timedelta(days=1)).timestamp()},
        {"title": "stale", "providerPublishTime": (now - timedelta(days=30)).timestamp()},
        {"title": "undated"},
        {"content": {"summary": "no headline"}},
        "not a dict",
    ]
    monkeypatch.setattr(fetch_mod, "_raw_news", lambda ticker, count: raw)
    titles = [d["title"] for d in fetch_ticker_news("X", lookback_days=7)]
    assert titles == ["fresh", "undated"]


def test_raw_news_falls_back_to_ticker_when_search_fails(monkeypatch):
    class BrokenSearch:
        def __init__(self, *a, **k):
            raise RuntimeError("boom")

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def get_news(self, count=10):
            return [{"title": f"{self.symbol} via ticker"}]

    monkeypatch.setattr(fetch_mod, "yf", SimpleNamespace(Search=BrokenSearch, Ticker=FakeTicker))
    assert [d["title"] for d in fetch_ticker_news("ZZZ")] == ["ZZZ via ticker"]

    class EmptySearch:
        def __init__(self, *a, **k):
            self.news = []

    class BrokenTicker:
        def __init__(self, symbol):
            pass

        def get_news(self, count=10):
            raise RuntimeError("down")

    monkeypatch.setattr(fetch_mod, "yf", SimpleNamespace(Search=EmptySearch, Ticker=BrokenTicker))
    assert fetch_ticker_news("ZZZ") == []
