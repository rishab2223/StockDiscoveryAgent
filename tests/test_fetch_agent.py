import json
from pathlib import Path

import pandas as pd

from sda import config
from sda.fetch import agent as fetch_agent
from sda.fetch.agent import fetch_market_data


def _history(symbols):
    idx = pd.bdate_range("2026-01-01", periods=30)
    return pd.DataFrame({(s, "Close"): [100.0 + i for i in range(30)] for s in symbols}, index=idx)


def _fundamentals(tickers, sectors, workers=None, refresh=False):
    results = {t: {"name": f"{t} Co", "sector": sectors.get(t) or "Technology", "pe": 12.0} for t in tickers if t != "NOFUND"}
    return results, [], {"cached": 1, "fetched": len(results) - 1}


def test_fetch_writes_market_json_with_gics_sectors(monkeypatch):
    universe = [
        {"symbol": "AAA", "sector": "Health Care", "name": "Alpha"},
        {"symbol": "BBB", "sector": "Financials", "name": "Beta"},
        {"symbol": "CCC", "sector": "Energy", "name": "Gamma"},
    ]
    monkeypatch.setattr(fetch_agent, "load_sp500", lambda refresh=False: universe)
    monkeypatch.setattr(fetch_agent, "download_history", lambda symbols: _history(["AAA", "BBB"]))
    monkeypatch.setattr(fetch_agent, "fetch_fundamentals_many", _fundamentals)

    payload = fetch_market_data(limit=2)
    run_dir = Path(payload["run_dir"])
    assert run_dir.parent == config.OUTPUT_DIR
    on_disk = json.loads((run_dir / "market.json").read_text(encoding="utf-8"))
    assert on_disk["universe"] == "sp500" and on_disk["ticker_count"] == 2
    assert on_disk["fundamentals_cached"] == 1 and on_disk["errors"] == []
    assert set(on_disk["tickers"]) == {"AAA", "BBB"}  # --limit 2 dropped CCC
    assert on_disk["tickers"]["AAA"]["sector"] == "Health Care"
    assert on_disk["tickers"]["AAA"]["price"] == 129.0 and on_disk["tickers"]["AAA"]["name"] == "AAA Co"
    assert "market_path" not in on_disk and payload["market_path"] == str(run_dir / "market.json")


def test_fetch_custom_tickers_and_missing_names(monkeypatch):
    monkeypatch.setattr(fetch_agent, "download_history", lambda symbols: _history(["XYZ"]))
    monkeypatch.setattr(fetch_agent, "fetch_fundamentals_many", _fundamentals)
    run_dir = config.OUTPUT_DIR / "given"

    payload = fetch_market_data(tickers=["xyz"], run_dir=str(run_dir))
    assert payload["universe"] == "custom" and payload["run_dir"] == str(run_dir)
    assert (run_dir / "market.json").exists()
    assert payload["tickers"]["XYZ"]["sector"] == "Information Technology"  # Yahoo label mapped
    assert payload["tickers"]["XYZ"]["name"] == "XYZ Co"


def test_fetch_drops_tickers_without_price_or_fundamentals(monkeypatch):
    monkeypatch.setattr(fetch_agent, "download_history", lambda symbols: _history(["XYZ"]))
    monkeypatch.setattr(fetch_agent, "fetch_fundamentals_many", _fundamentals)
    payload = fetch_market_data(tickers=["XYZ", "NOFUND"])
    assert set(payload["tickers"]) == {"XYZ"}
    assert payload["errors"] == [{"ticker": "NOFUND", "error": "no price or fundamentals"}]
