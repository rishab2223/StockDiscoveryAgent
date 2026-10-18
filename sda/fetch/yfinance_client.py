from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from sda.config import FUNDAMENTAL_WORKERS, HISTORY_PERIOD, INFO_RETRIES, TRADING_DAYS_1M, TRADING_DAYS_1W
from sda.sectors import normalize_sector


def _series_close(hist: pd.DataFrame, ticker: str) -> pd.Series:
    if hist is None or hist.empty:
        return pd.Series(dtype=float)
    if isinstance(hist.columns, pd.MultiIndex):
        level0 = hist.columns.get_level_values(0)
        if ticker in level0:
            close = hist[ticker]["Close"]
        elif "Close" in level0:
            close = hist["Close"][ticker]
        else:
            return pd.Series(dtype=float)
    else:
        if "Close" not in hist.columns:
            return pd.Series(dtype=float)
        close = hist["Close"]
    return pd.to_numeric(close, errors="coerce").dropna()


def _pct_change(closes: pd.Series, lookback: int) -> float | None:
    if len(closes) < lookback + 1:
        return None
    last = float(closes.iloc[-1])
    prior = float(closes.iloc[-(lookback + 1)])
    if prior == 0:
        return None
    return (last - prior) / prior


def download_history(tickers: list[str]) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()
    return yf.download(
        tickers=tickers,
        period=HISTORY_PERIOD,
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )


def price_snapshot(hist: pd.DataFrame, ticker: str) -> dict[str, Any]:
    closes = _series_close(hist, ticker)
    if closes.empty:
        return {"price": None, "price_as_of": None, "pct_1w": None, "pct_1m": None}
    return {
        "price": float(closes.iloc[-1]),
        "price_as_of": str(closes.index[-1].date()),
        "pct_1w": _pct_change(closes, TRADING_DAYS_1W),
        "pct_1m": _pct_change(closes, TRADING_DAYS_1M),
    }


def _row_history(frame: pd.DataFrame | None, row_names: tuple[str, ...]) -> list[float]:
    """Annual values for the first matching statement row, newest first."""
    if frame is None or frame.empty:
        return []
    idx = {str(i).strip().lower(): i for i in frame.index}
    for name in row_names:
        key = name.lower()
        if key in idx:
            values = pd.to_numeric(frame.loc[idx[key]], errors="coerce").dropna().tolist()
            return [float(v) for v in values]
    return []


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        if np.isnan(number) or np.isinf(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _statement(stock: yf.Ticker, attr: str) -> pd.DataFrame | None:
    try:
        return getattr(stock, attr)
    except Exception:
        return None


def _info_with_retry(stock: yf.Ticker, retries: int) -> dict[str, Any]:
    """Yahoo answers throttled .info requests with an empty dict rather than an error."""
    info: dict[str, Any] = {}
    for attempt in range(retries + 1):
        try:
            info = stock.info or {}
        except Exception:
            info = {}
        if info.get("marketCap") or info.get("trailingPE") or info.get("sharesOutstanding"):
            return info
        if attempt < retries:
            time.sleep(1.0 + attempt)
    return info


def fetch_fundamentals(ticker: str, sector: str | None = None) -> dict[str, Any]:
    """One ticker: Yahoo .info plus annual income-statement and cash-flow rows.

    `sector` is the GICS label from the index list and wins over Yahoo's own
    taxonomy; `info_missing` tells the caller the reply was throttled."""
    stock = yf.Ticker(ticker)
    info = _info_with_retry(stock, INFO_RETRIES)
    financials = _statement(stock, "financials")
    cashflow = _statement(stock, "cashflow")

    return {
        "name": info.get("shortName") or info.get("longName") or ticker,
        "sector": sector or normalize_sector(info.get("sector")),
        "market_cap": _safe_float(info.get("marketCap")),
        "enterprise_value": _safe_float(info.get("enterpriseValue")),
        "pe": _safe_float(info.get("trailingPE")),
        "forward_pe": _safe_float(info.get("forwardPE")),
        "ps": _safe_float(info.get("priceToSalesTrailing12Months")),
        "pb": _safe_float(info.get("priceToBook")),
        "peg": _safe_float(info.get("pegRatio")),
        "gross_margin": _safe_float(info.get("grossMargins")),
        "operating_margin": _safe_float(info.get("operatingMargins")),
        "profit_margin": _safe_float(info.get("profitMargins")),
        "roe": _safe_float(info.get("returnOnEquity")),
        "free_cashflow_ttm": _safe_float(info.get("freeCashflow")),
        "net_income_annual": _row_history(financials, ("Net Income", "Net Income Common Stockholders")),
        "ebit_annual": _row_history(financials, ("EBIT", "Operating Income")),
        "revenue_annual": _row_history(financials, ("Total Revenue", "Operating Revenue")),
        "fcf_annual": _row_history(cashflow, ("Free Cash Flow",)),
        "shares": _safe_float(info.get("sharesOutstanding")),
        "info_missing": not info,
    }


def fetch_fundamentals_many(
    tickers: list[str],
    sectors: dict[str, str],
    workers: int = FUNDAMENTAL_WORKERS,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    results: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []

    def _one(symbol: str) -> tuple[str, dict[str, Any] | None, str | None]:
        try:
            return symbol, fetch_fundamentals(symbol, sectors.get(symbol)), None
        except Exception as exc:
            return symbol, None, str(exc)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, ticker) for ticker in tickers]
        for future in as_completed(futures):
            symbol, payload, error = future.result()
            if payload is None:
                errors.append({"ticker": symbol, "error": error or "unknown"})
                continue
            if payload.pop("info_missing"):
                # Keep the partial record so prices still rank movers, but report it.
                errors.append({"ticker": symbol, "error": "Yahoo .info empty after retries; fundamentals partial"})
            results[symbol] = payload
    return results, errors
