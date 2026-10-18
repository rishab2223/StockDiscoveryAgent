import json

import pandas as pd

from sda import config
from sda.fetch import yfinance_client as client
from sda.fetch.yfinance_client import _pct_change, _row_history, _safe_float, fetch_fundamentals_many, price_snapshot


def _closes(n: int, start: float = 100.0) -> list[float]:
    return [start + i for i in range(n)]


def _frame(prices: dict[str, list[float]], ticker_first: bool = True) -> pd.DataFrame:
    n = len(next(iter(prices.values())))
    idx = pd.bdate_range("2026-01-01", periods=n)
    cols = {((t, "Close") if ticker_first else ("Close", t)): v for t, v in prices.items()}
    return pd.DataFrame(cols, index=idx)


def test_price_snapshot_multiindex_both_orientations():
    closes = _closes(30)
    for ticker_first in (True, False):
        snap = price_snapshot(_frame({"AAA": closes}, ticker_first), "AAA")
        assert snap["price"] == 129.0
        assert snap["price_as_of"] == "2026-02-11"
        assert snap["pct_1w"] == (129 - 124) / 124
        assert snap["pct_1m"] == (129 - 108) / 108


def test_price_snapshot_single_level_and_missing():
    single = pd.DataFrame({"Close": _closes(10)}, index=pd.bdate_range("2026-01-01", periods=10))
    snap = price_snapshot(single, "AAA")
    assert snap["price"] == 109.0 and snap["pct_1w"] == (109 - 104) / 104 and snap["pct_1m"] is None
    empty = {"price": None, "price_as_of": None, "pct_1w": None, "pct_1m": None}
    assert price_snapshot(pd.DataFrame(), "AAA") == empty
    assert price_snapshot(_frame({"BBB": _closes(5)}), "AAA") == empty
    assert price_snapshot(pd.DataFrame({"Open": [1.0]}), "AAA") == empty


def test_pct_change_guards():
    s = pd.Series([0.0, 1.0, 2.0])
    assert _pct_change(s, 5) is None
    assert _pct_change(s, 2) is None  # prior close of zero
    assert _pct_change(s, 1) == 1.0


def test_row_history_and_safe_float():
    frame = pd.DataFrame({"2025": [10, 1], "2024": [8, None]}, index=["Net Income ", "EBIT"])
    assert _row_history(frame, ("Net Income",)) == [10.0, 8.0]
    assert _row_history(frame, ("Missing", "EBIT")) == [1.0]
    assert _row_history(None, ("x",)) == [] and _row_history(pd.DataFrame(), ("x",)) == []
    assert _safe_float("3.5") == 3.5
    assert _safe_float(float("nan")) is None and _safe_float(None) is None and _safe_float("x") is None


def test_fundamentals_cache_and_partial_records(monkeypatch):
    calls = []

    def fake_fetch(symbol, sector=None):
        calls.append(symbol)
        if symbol == "ERR":
            raise RuntimeError("boom")
        return {"name": symbol, "sector": sector, "pe": 10.0, "info_missing": symbol == "THROTTLED"}

    monkeypatch.setattr(client, "fetch_fundamentals", fake_fetch)
    sectors = {"AAA": "Energy"}

    results, errors, stats = fetch_fundamentals_many(["AAA", "THROTTLED", "ERR"], sectors, workers=2)
    assert stats == {"cached": 0, "fetched": 3}
    assert results["AAA"] == {"name": "AAA", "sector": "Energy", "pe": 10.0}
    assert "info_missing" not in results["THROTTLED"]
    assert {e["ticker"] for e in errors} == {"THROTTLED", "ERR"}
    cached = config.CACHE_DIR / "fundamentals"
    assert (cached / "AAA.json").exists() and not (cached / "THROTTLED.json").exists()
    assert json.loads((cached / "AAA.json").read_text())["pe"] == 10.0

    calls.clear()
    results, errors, stats = fetch_fundamentals_many(["AAA", "THROTTLED"], sectors, workers=2)
    assert calls == ["THROTTLED"] and stats == {"cached": 1, "fetched": 1}

    calls.clear()
    fetch_fundamentals_many(["AAA"], sectors, workers=2, refresh=True)
    assert calls == ["AAA"]

    monkeypatch.setattr(config, "FUNDAMENTALS_TTL_HOURS", 0)
    calls.clear()
    fetch_fundamentals_many(["AAA"], sectors, workers=2)
    assert calls == ["AAA"]  # expired


def test_info_retry_sleeps_then_gives_up(monkeypatch):
    naps = []
    monkeypatch.setattr(client.time, "sleep", naps.append)

    class Stock:
        info = {}

    assert client._info_with_retry(Stock(), retries=2) == {}
    assert naps == [1.0, 2.0]

    class Flaky:
        def __init__(self):
            self.n = 0

        @property
        def info(self):
            self.n += 1
            if self.n == 1:
                raise RuntimeError("429")
            return {"marketCap": 1}

    naps.clear()
    assert client._info_with_retry(Flaky(), retries=2) == {"marketCap": 1}
    assert naps == [1.0]
