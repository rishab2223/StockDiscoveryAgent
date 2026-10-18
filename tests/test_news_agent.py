import json
from pathlib import Path

import pytest

from sda import config
from sda.news import agent as news_agent
from sda.news.agent import analyze_news
from tests.conftest import sample_screen, write_run


def _fake_news(ticker, lookback_days=None):
    return {
        "AAA": [
            {"ticker": "AAA", "title": "Alpha announces earnings", "publisher": "PR", "related_tickers": ["AAA"]},
            {"ticker": "AAA", "title": "Alpha announces earnings", "publisher": "PR", "related_tickers": ["AAA"]},
            {"ticker": "AAA", "title": "Analyst upgrades Alpha", "publisher": "Street", "related_tickers": ["AAA"]},
            {"ticker": "AAA", "title": "Alpha shares drift", "publisher": "Wire", "related_tickers": ["AAA"]},
            {"ticker": "AAA", "title": "Beta earnings beat", "publisher": "Wire", "related_tickers": ["BBB"]},
        ],
        "BBB": [],
    }[ticker]


def test_analyze_news_writes_cleaned_payload(monkeypatch):
    run_dir = write_run(config.OUTPUT_DIR / "2026-10-01_000000Z", screen=sample_screen())
    monkeypatch.setattr(news_agent, "fetch_ticker_news", _fake_news)
    calls = []

    def fake_classify(items):
        calls.append(len(items))
        return [{**item, "final_label": "drop", "llm_reason": "off"} for item in items]

    monkeypatch.setattr(news_agent, "classify_ambiguous", fake_classify)

    payload = analyze_news()
    assert payload["run_dir"] == str(run_dir)
    on_disk = json.loads((run_dir / "news_clean.json").read_text(encoding="utf-8"))
    assert on_disk["screen_as_of"] == "2026-10-01T00:00:00+00:00"
    assert on_disk["lookback_days"] == config.NEWS_LOOKBACK_DAYS
    aaa = on_disk["tickers"]["AAA"]
    assert aaa["buckets"] == ["undervalued", "dev_1w"]
    assert aaa["raw_count"] == 4  # story about BBB was not about AAA
    assert [item["title"] for item in aaa["kept"]] == ["Alpha announces earnings"]
    assert aaa["dropped_count"] == 2  # analyst piece + unresolved "maybe"
    assert on_disk["tickers"]["BBB"] == {"buckets": ["undervalued"], "kept": [], "dropped_count": 0, "raw_count": 0}
    assert calls == [1]  # one classifier batch for every ticker's leftovers
    assert "screen" not in payload and "kept_documents" not in aaa


def test_analyze_news_uses_explicit_screen_outside_output(monkeypatch, tmp_path):
    elsewhere = write_run(tmp_path / "elsewhere", screen=sample_screen())
    monkeypatch.setattr(news_agent, "fetch_ticker_news", lambda t, lookback_days=None: [])
    payload = analyze_news(screen_path=str(elsewhere / "screen.json"), lookback_days=3)
    assert payload["lookback_days"] == 3
    run_dir = Path(payload["run_dir"])
    assert run_dir.parent == config.OUTPUT_DIR  # a fresh run folder, not "elsewhere"
    assert (run_dir / "news_clean.json").exists()


def test_analyze_news_requires_screen():
    write_run(config.OUTPUT_DIR / "2026-10-01_000000Z")
    with pytest.raises(FileNotFoundError):
        analyze_news()
