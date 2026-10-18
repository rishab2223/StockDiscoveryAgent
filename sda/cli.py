from __future__ import annotations

import argparse
import json

from sda.config import SCREEN_N


def _tickers(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [part.strip().upper() for part in raw.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sda",
        description="Stock Discovery Agent: fetch US stocks, screen lists, clean news, write GPT verdicts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Data Fetcher: yfinance -> cache")
    fetch.add_argument("--limit", type=int, default=None, help="Only the first N S&P 500 names")
    fetch.add_argument("--tickers", type=str, default=None, help="Comma-separated override list")
    fetch.add_argument("--refresh", action="store_true", help="Ignore cached universe and fundamentals")

    screen = sub.add_parser("screen", help="Screening Agent: cache -> 20x4 lists")
    screen.add_argument("--n", type=int, default=SCREEN_N)
    screen.add_argument("--cache", dest="cache_path", default=None)

    news = sub.add_parser("news", help="News Analyser: Yahoo news + noise filter")
    news.add_argument("--screen", dest="screen_path", default=None)

    verdict = sub.add_parser("verdict", help="OpenAI verdicts -> watchlist file")
    verdict.add_argument("--news", dest="news_path", default=None)
    verdict.add_argument("--screen", dest="screen_path", default=None)

    run = sub.add_parser("run", help="LangGraph: fetch -> screen -> news -> verdict")
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--tickers", type=str, default=None)
    run.add_argument("--n", type=int, default=SCREEN_N)
    run.add_argument("--cache", dest="cache_path", default=None)
    run.add_argument("--skip-fetch", action="store_true")
    run.add_argument("--refresh", action="store_true", help="Ignore cached universe and fundamentals")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "fetch":
        from sda.fetch.agent import fetch_market_data

        payload = fetch_market_data(limit=args.limit, tickers=_tickers(args.tickers), refresh=args.refresh)
        summary = {k: payload.get(k) for k in ("run_dir", "cache_path", "ticker_count", "fundamentals_cached")}
        print(json.dumps(summary, indent=2))
        return 0

    if args.command == "screen":
        from sda.screen.agent import run_screen

        payload = run_screen(n=args.n, cache_path=args.cache_path)
        counts = {k: len(v) for k, v in payload["lists"].items()}
        print(json.dumps({"run_dir": payload.get("run_dir"), "screen_path": payload["screen_path"], "counts": counts}, indent=2))
        return 0

    if args.command == "news":
        from sda.news.agent import analyze_news

        payload = analyze_news(screen_path=args.screen_path)
        print(json.dumps({"run_dir": payload.get("run_dir"), "news_path": payload["news_path"], "tickers": len(payload["tickers"])}, indent=2))
        return 0

    if args.command == "verdict":
        from sda.verdict.agent import write_verdicts

        payload = write_verdicts(news_path=args.news_path, screen_path=args.screen_path)
        print(json.dumps({"run_dir": payload.get("run_dir"), "verdicts_path": payload["verdicts_path"], "count": len(payload["verdicts"])}, indent=2))
        return 0

    if args.command == "run":
        from sda.graph.pipeline import run_pipeline

        state = run_pipeline(
            limit=args.limit,
            tickers=_tickers(args.tickers),
            n=args.n,
            cache_path=args.cache_path,
            skip_fetch=args.skip_fetch,
            refresh=args.refresh,
        )
        print(
            json.dumps(
                {k: state.get(k) for k in ("run_dir", "cache_path", "screen_path", "news_path", "verdicts_path")},
                indent=2,
            )
        )
        return 0

    return 1
