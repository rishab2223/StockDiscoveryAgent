from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sda.config import NEWS_LOOKBACK_DAYS
from sda.io_util import read_json, write_json
from sda.news.classifier import classify_ambiguous
from sda.news.fetch import fetch_ticker_news
from sda.news.filter import filter_news, mentions_company
from sda.run_dir import file_in_run, resolve_run_dir
from sda.screen.agent import index_screen


def _load_screen(screen_path: str | None, run_dir: Path) -> dict[str, Any]:
    if screen_path:
        return read_json(Path(screen_path))
    found = file_in_run(run_dir, "screen.json")
    if found is None:
        raise FileNotFoundError(f"No screen.json in {run_dir}. Run `python -m sda screen` first.")
    return read_json(found)


def analyze_news(
    screen_path: str | None = None,
    lookback_days: int = NEWS_LOOKBACK_DAYS,
    run_dir: str | None = None,
) -> dict[str, Any]:
    """Fetch Yahoo news for screened names, drop noise, keep company-originated items."""
    folder = resolve_run_dir(run_dir, hint_path=screen_path)
    screen = _load_screen(screen_path, folder)
    by_ticker: dict[str, Any] = {}

    for ticker, row in index_screen(screen).items():
        raw = fetch_ticker_news(ticker, lookback_days=lookback_days)
        raw = [item for item in raw if mentions_company(item, ticker, row.get("name"))]
        split = filter_news(raw)
        maybe_resolved = classify_ambiguous(split["maybe"])
        kept = list(split["keep"])
        dropped = list(split["drop"])
        for item in maybe_resolved:
            if item.get("final_label") == "keep":
                kept.append(item)
            else:
                dropped.append(item)
        by_ticker[ticker] = {
            "buckets": row["buckets"],
            "kept": kept,
            "dropped_count": len(dropped),
            "raw_count": len(raw),
        }

    as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    path = folder / "news_clean.json"
    payload = {
        "as_of": as_of,
        "screen_as_of": screen.get("as_of"),
        "lookback_days": lookback_days,
        "tickers": by_ticker,
    }
    write_json(path, payload)
    payload["news_path"] = str(path)
    payload["run_dir"] = str(folder)
    return payload
