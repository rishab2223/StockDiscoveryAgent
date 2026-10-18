from __future__ import annotations

import io
from urllib.request import Request, urlopen

import pandas as pd

from sda import config
from sda.fetch import cache

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
DATASETS_CSV = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
)
USER_AGENT = "StockDiscoveryAgent/0.1 (personal research)"


def _read_url(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _normalize_symbol(symbol: str) -> str:
    """Wikipedia writes BRK.B; Yahoo wants BRK-B."""
    return symbol.strip().replace(".", "-").upper()


def _rows_from_frame(frame: pd.DataFrame) -> list[dict[str, str]]:
    symbol_col = "Symbol" if "Symbol" in frame.columns else frame.columns[0]
    sector_col = "GICS Sector" if "GICS Sector" in frame.columns else "Sector"
    name_col = "Security" if "Security" in frame.columns else "Name"
    rows = []
    for _, row in frame.iterrows():
        symbol = _normalize_symbol(str(row[symbol_col]))
        if not symbol or symbol == "NAN":
            continue
        rows.append(
            {
                "symbol": symbol,
                "sector": str(row.get(sector_col) or "Unknown"),
                "name": str(row.get(name_col) or symbol),
            }
        )
    return rows


def _download_sp500() -> list[dict[str, str]]:
    try:
        rows = _rows_from_frame(pd.read_html(io.StringIO(_read_url(WIKI_URL)))[0])
        if rows:
            return rows
    except Exception:
        pass
    rows = _rows_from_frame(pd.read_csv(io.StringIO(_read_url(DATASETS_CSV))))
    if not rows:
        raise RuntimeError("Could not load S&P 500 constituents from Wikipedia or fallback CSV.")
    return rows


def load_sp500(refresh: bool = False) -> list[dict[str, str]]:
    """[{symbol, sector, name}] for current S&P 500 names, cached for UNIVERSE_TTL_DAYS."""
    if not refresh:
        cached = cache.load("universe", "sp500", config.UNIVERSE_TTL_DAYS * 86400)
        if cached:
            return cached
    rows = _download_sp500()
    cache.store("universe", "sp500", rows)
    return rows
