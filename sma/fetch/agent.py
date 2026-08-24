from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sma.fetch.universe import load_sp500
from sma.fetch.yfinance_client import download_history, fetch_fundamentals_many, price_snapshot
from sma.io_util import write_json
from sma.run_dir import new_run_dir


def fetch_market_data(
    limit: int | None = None,
    tickers: list[str] | None = None,
    cache_path: str | None = None,
    run_dir: str | None = None,
) -> dict[str, Any]:
    """Pull S&P 500 (or an override list) from yfinance and write market.json in the run folder."""
    folder = Path(run_dir) if run_dir else (Path(cache_path).parent if cache_path else new_run_dir())
    folder.mkdir(parents=True, exist_ok=True)
    as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    universe_rows = []
    if tickers:
        universe_rows = [{"symbol": t.upper(), "sector": "Unknown", "name": t.upper()} for t in tickers]
    else:
        universe_rows = load_sp500()
        if limit:
            universe_rows = universe_rows[:limit]

    symbols = [row["symbol"] for row in universe_rows]
    wiki_sectors = {row["symbol"]: row["sector"] for row in universe_rows}
    wiki_names = {row["symbol"]: row["name"] for row in universe_rows}

    history = download_history(symbols)
    fundamentals, errors = fetch_fundamentals_many(symbols, wiki_sectors)

    records: dict[str, Any] = {}
    for symbol in symbols:
        snapshot = price_snapshot(history, symbol)
        fund = fundamentals.get(symbol, {})
        if snapshot["price"] is None and not fund:
            errors.append({"ticker": symbol, "error": "no price or fundamentals"})
            continue
        records[symbol] = {
            **snapshot,
            **fund,
            "name": fund.get("name") or wiki_names.get(symbol, symbol),
            "sector": fund.get("sector") or wiki_sectors.get(symbol, "Unknown"),
        }

    path = Path(cache_path) if cache_path else folder / "market.json"
    payload = {
        "as_of": as_of,
        "universe": "custom" if tickers else "sp500",
        "ticker_count": len(records),
        "tickers": records,
        "errors": errors,
        "source": "yfinance",
    }
    write_json(path, payload)
    payload["cache_path"] = str(path)
    payload["run_dir"] = str(folder)
    return payload
