import pandas as pd
import pytest

from sda.fetch import universe
from sda.fetch.universe import _rows_from_frame, load_sp500


def test_rows_from_wikipedia_and_fallback_columns():
    wiki = pd.DataFrame({"Symbol": ["BRK.B", " aapl "], "Security": ["Berkshire", "Apple"], "GICS Sector": ["Financials", "Information Technology"]})
    assert _rows_from_frame(wiki) == [
        {"symbol": "BRK-B", "sector": "Financials", "name": "Berkshire"},
        {"symbol": "AAPL", "sector": "Information Technology", "name": "Apple"},
    ]
    csv = pd.DataFrame({"Symbol": ["MMM", float("nan")], "Name": ["3M", "x"], "Sector": ["Industrials", "y"]})
    assert _rows_from_frame(csv) == [{"symbol": "MMM", "sector": "Industrials", "name": "3M"}]


def test_load_sp500_caches_and_refreshes(monkeypatch):
    downloads = []

    def fake_download():
        downloads.append(1)
        return [{"symbol": "AAA", "sector": "Energy", "name": "A"}]

    monkeypatch.setattr(universe, "_download_sp500", fake_download)
    assert load_sp500()[0]["symbol"] == "AAA"
    assert load_sp500() == [{"symbol": "AAA", "sector": "Energy", "name": "A"}]
    assert len(downloads) == 1
    load_sp500(refresh=True)
    assert len(downloads) == 2


def test_download_falls_back_to_csv(monkeypatch):
    def read(url):
        if "wikipedia" in url:
            raise OSError("blocked")
        return "Symbol,Name,Sector\nMMM,3M,Industrials\n"

    monkeypatch.setattr(universe, "_read_url", read)
    assert universe._download_sp500() == [{"symbol": "MMM", "sector": "Industrials", "name": "3M"}]

    monkeypatch.setattr(universe, "_read_url", lambda url: "Symbol,Name,Sector\n")
    with pytest.raises(RuntimeError):
        universe._download_sp500()
