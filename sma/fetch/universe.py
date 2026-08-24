from __future__ import annotations

import io
from urllib.request import Request, urlopen

import pandas as pd

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
DATASETS_CSV = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
)
USER_AGENT = "stockMarketAnalysisAgent/0.1 (personal research)"


def _read_url(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().replace(".", "-").upper()


def load_sp500() -> list[dict[str, str]]:
    """Return [{symbol, sector, name}] for current S&P 500 names."""
    try:
        html = _read_url(WIKI_URL)
        tables = pd.read_html(io.StringIO(html))
        frame = tables[0]
        symbol_col = "Symbol"
        sector_col = "GICS Sector" if "GICS Sector" in frame.columns else "Sector"
        name_col = "Security" if "Security" in frame.columns else "Name"
        rows = []
        for _, row in frame.iterrows():
            rows.append(
                {
                    "symbol": _normalize_symbol(str(row[symbol_col])),
                    "sector": str(row.get(sector_col) or "Unknown"),
                    "name": str(row.get(name_col) or row[symbol_col]),
                }
            )
        if rows:
            return rows
    except Exception:
        pass

    csv_text = _read_url(DATASETS_CSV)
    frame = pd.read_csv(io.StringIO(csv_text))
    symbol_col = "Symbol" if "Symbol" in frame.columns else frame.columns[0]
    sector_col = "GICS Sector" if "GICS Sector" in frame.columns else "Sector"
    name_col = "Security" if "Security" in frame.columns else "Name"
    rows = []
    for _, row in frame.iterrows():
        rows.append(
            {
                "symbol": _normalize_symbol(str(row[symbol_col])),
                "sector": str(row.get(sector_col) or "Unknown"),
                "name": str(row.get(name_col) or row[symbol_col]),
            }
        )
    if not rows:
        raise RuntimeError("Could not load S&P 500 constituents from Wikipedia or fallback CSV.")
    return rows
