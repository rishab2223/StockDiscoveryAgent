from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sda.fetch.universe import load_sp500
from sda.fetch.yfinance_client import download_history, fetch_fundamentals_many, price_snapshot
from sda.io_util import write_json
from sda.run_dir import new_run_dir
from sda.sectors import normalize_sector


def fetch_market_data(
    limit: int | None = None,
    tickers: list[str] | None = None,
    run_dir: str | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Pull the S&P 500 (or an explicit ticker list) from Yahoo and write market.json
    into the run folder. `refresh` bypasses the universe and fundamentals caches."""
    folder = Path(run_dir) if run_dir else new_run_dir()
    folder.mkdir(parents=True, exist_ok=True)
    as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    if tickers:
        universe_rows = [{"symbol": t.upper(), "sector": None, "name": None} for t in tickers]
    else:
        universe_rows = load_sp500(refresh=refresh)
        if limit:
            universe_rows = universe_rows[:limit]

    symbols = [row["symbol"] for row in universe_rows]
    sectors = {row["symbol"]: row["sector"] for row in universe_rows if row["sector"]}
    names = {row["symbol"]: row["name"] for row in universe_rows if row["name"]}

    history = download_history(symbols)
    fundamentals, errors, stats = fetch_fundamentals_many(symbols, sectors, refresh=refresh)

    records: dict[str, Any] = {}
    for symbol in symbols:
        snapshot = price_snapshot(history, symbol)
        fund = fundamentals.get(symbol)
        if snapshot["price"] is None and fund is None:
            errors.append({"ticker": symbol, "error": "no price or fundamentals"})
            continue
        fund = fund or {}
        records[symbol] = {
            **snapshot,
            **fund,
            "name": fund.get("name") or names.get(symbol) or symbol,
            "sector": normalize_sector(fund.get("sector") or sectors.get(symbol)),
        }

    path = folder / "market.json"
    payload = {
        "as_of": as_of,
        "universe": "custom" if tickers else "sp500",
        "source": "yfinance",
        "ticker_count": len(records),
        "fundamentals_cached": stats["cached"],
        "tickers": records,
        "errors": errors,
    }
    write_json(path, payload)
    payload["market_path"] = str(path)
    payload["run_dir"] = str(folder)
    return payload
