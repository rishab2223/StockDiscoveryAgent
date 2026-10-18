from __future__ import annotations

import argparse
import json
from typing import Any

from sda.config import SCREEN_N


def _tickers(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [part.strip().upper() for part in raw.split(",") if part.strip()]


def _print(summary: dict[str, Any]) -> None:
    print(json.dumps(summary, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sda",
        description="Stock Discovery Agent: fetch US stocks, screen lists, clean news, write GPT verdicts.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Yahoo data for the S&P 500 -> new run folder / market.json")
    fetch.add_argument("--limit", type=int, default=None, help="Only the first N S&P 500 names")
    fetch.add_argument("--tickers", type=str, default=None, help="Comma-separated override list")
    fetch.add_argument("--refresh", action="store_true", help="Ignore cached universe and fundamentals")

    screen = sub.add_parser("screen", help="Rank the fetched universe into four lists of N")
    screen.add_argument("--n", type=int, default=SCREEN_N, help="Names per list")
    screen.add_argument("--market", dest="market_path", default=None, help="market.json to screen (default: latest run)")

    news = sub.add_parser("news", help="Yahoo news for shortlisted names + noise filter")
    news.add_argument("--screen", dest="screen_path", default=None, help="screen.json to use (default: latest run)")

    verdict = sub.add_parser("verdict", help="OpenAI verdicts -> watchlist file")
    verdict.add_argument("--news", dest="news_path", default=None)
    verdict.add_argument("--screen", dest="screen_path", default=None)

    run = sub.add_parser("run", help="LangGraph: fetch -> screen -> news -> verdict")
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--tickers", type=str, default=None)
    run.add_argument("--n", type=int, default=SCREEN_N)
    run.add_argument("--market", dest="market_path", default=None, help="market.json to reuse with --skip-fetch")
    run.add_argument("--skip-fetch", action="store_true", help="Reuse --market or the newest earlier market.json")
    run.add_argument("--refresh", action="store_true", help="Ignore cached universe and fundamentals")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "fetch":
        from sda.fetch.agent import fetch_market_data

        payload = fetch_market_data(limit=args.limit, tickers=_tickers(args.tickers), refresh=args.refresh)
        _print(
            {
                "run_dir": payload["run_dir"],
                "market_path": payload["market_path"],
                "ticker_count": payload["ticker_count"],
                "fundamentals_cached": payload["fundamentals_cached"],
                "errors": len(payload["errors"]),
            }
        )
    elif args.command == "screen":
        from sda.screen.agent import run_screen

        payload = run_screen(n=args.n, market_path=args.market_path)
        counts = {k: len(v) for k, v in payload["lists"].items()}
        _print({"run_dir": payload["run_dir"], "screen_path": payload["screen_path"], "counts": counts})
    elif args.command == "news":
        from sda.news.agent import analyze_news

        payload = analyze_news(screen_path=args.screen_path)
        kept = sum(len(v["kept"]) for v in payload["tickers"].values())
        _print(
            {
                "run_dir": payload["run_dir"],
                "news_path": payload["news_path"],
                "tickers": len(payload["tickers"]),
                "kept_items": kept,
            }
        )
    elif args.command == "verdict":
        from sda.verdict.agent import write_verdicts

        payload = write_verdicts(news_path=args.news_path, screen_path=args.screen_path)
        _print({"run_dir": payload["run_dir"], "verdicts_path": payload["verdicts_path"], "count": len(payload["verdicts"])})
    elif args.command == "run":
        from sda.graph.pipeline import run_pipeline

        state = run_pipeline(
            limit=args.limit,
            tickers=_tickers(args.tickers),
            n=args.n,
            market_path=args.market_path,
            skip_fetch=args.skip_fetch,
            refresh=args.refresh,
        )
        _print({k: state.get(k) for k in ("run_dir", "market_path", "screen_path", "news_path", "verdicts_path")})
    return 0
