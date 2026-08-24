from __future__ import annotations

from langchain_core.tools import tool

from sma.fetch.agent import fetch_market_data
from sma.news.agent import analyze_news
from sma.screen.agent import run_screen
from sma.verdict.agent import write_verdicts


@tool
def fetch_market_data_tool(limit: int = 0) -> str:
    """Download S&P 500 (or a limited prefix) market data from yfinance into the cache."""
    payload = fetch_market_data(limit=limit or None)
    return payload.get("cache_path") or ""


@tool
def run_screen_tool(n: int = 20, cache_path: str = "") -> str:
    """Score the latest (or given) cache and write undervalued/overvalued/deviation lists."""
    payload = run_screen(n=n, cache_path=cache_path or None)
    return payload.get("screen_path") or ""


@tool
def analyze_news_tool(screen_path: str = "") -> str:
    """Fetch Yahoo news for screened tickers and write the cleaned news JSON."""
    payload = analyze_news(screen_path=screen_path or None)
    return payload.get("news_path") or ""


@tool
def write_verdicts_tool(news_path: str = "", screen_path: str = "") -> str:
    """Run the OpenAI verdict chain and write the watchlist file."""
    payload = write_verdicts(news_path=news_path or None, screen_path=screen_path or None)
    return payload.get("verdicts_path") or ""
