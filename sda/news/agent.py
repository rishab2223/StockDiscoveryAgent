from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sda import config
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
    lookback_days: int | None = None,
    run_dir: str | None = None,
) -> dict[str, Any]:
    """Fetch Yahoo news for every shortlisted ticker (in parallel), keep stories that
    are about the company, drop analyst/opinion noise, and write news_clean.json."""
    folder = resolve_run_dir(run_dir, hint_path=screen_path)
    screen = _load_screen(screen_path, folder)
    rows = index_screen(screen)
    lookback = lookback_days or config.NEWS_LOOKBACK_DAYS

    def _one(ticker: str) -> tuple[str, list[dict[str, Any]]]:
        raw = fetch_ticker_news(ticker, lookback_days=lookback)
        name = rows[ticker].get("name")
        return ticker, [item for item in raw if mentions_company(item, ticker, name)]

    with ThreadPoolExecutor(max_workers=config.NEWS_WORKERS) as pool:
        about_company = dict(pool.map(_one, rows))

    # One classifier batch for every ticker's leftovers instead of one per ticker.
    split = {ticker: filter_news(items) for ticker, items in about_company.items()}
    resolved = classify_ambiguous([item for parts in split.values() for item in parts["maybe"]])
    maybe_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for item in resolved:
        maybe_by_ticker.setdefault(item["ticker"], []).append(item)

    by_ticker: dict[str, Any] = {}
    for ticker, row in rows.items():
        parts = split[ticker]
        kept = list(parts["keep"])
        dropped = list(parts["drop"])
        for item in maybe_by_ticker.get(ticker, []):
            (kept if item.get("final_label") == "keep" else dropped).append(item)
        by_ticker[ticker] = {
            "buckets": row["buckets"],
            "kept": kept,
            "dropped_count": len(dropped),
            "raw_count": len(about_company[ticker]),
        }

    path = folder / "news_clean.json"
    payload = {
        "as_of": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "screen_as_of": screen.get("as_of"),
        "lookback_days": lookback,
        "tickers": by_ticker,
    }
    write_json(path, payload)
    payload["news_path"] = str(path)
    payload["run_dir"] = str(folder)
    return payload
