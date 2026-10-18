from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from sda.config import SCREEN_N
from sda.fetch.agent import fetch_market_data
from sda.graph.state import PipelineState
from sda.news.agent import analyze_news
from sda.run_dir import latest_run_with, new_run_dir
from sda.screen.agent import run_screen
from sda.verdict.agent import write_verdicts


def fetch_node(state: PipelineState) -> dict[str, Any]:
    if state.get("skip_fetch"):
        return {}
    payload = fetch_market_data(
        limit=state.get("limit"),
        tickers=state.get("tickers"),
        run_dir=state.get("run_dir"),
        refresh=bool(state.get("refresh")),
    )
    return {"market_path": payload["market_path"], "run_dir": payload["run_dir"]}


def screen_node(state: PipelineState) -> dict[str, Any]:
    payload = run_screen(
        n=state.get("n") or SCREEN_N,
        market_path=state.get("market_path"),
        run_dir=state.get("run_dir"),
    )
    return {"screen_path": payload["screen_path"], "run_dir": payload["run_dir"]}


def news_node(state: PipelineState) -> dict[str, Any]:
    payload = analyze_news(screen_path=state.get("screen_path"), run_dir=state.get("run_dir"))
    return {"news_path": payload["news_path"], "run_dir": payload["run_dir"]}


def verdict_node(state: PipelineState) -> dict[str, Any]:
    payload = write_verdicts(
        news_path=state.get("news_path"),
        screen_path=state.get("screen_path"),
        run_dir=state.get("run_dir"),
    )
    return {
        "verdicts_path": payload["verdicts_path"],
        "markdown_path": payload["markdown_path"],
        "run_dir": payload["run_dir"],
    }


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("fetch", fetch_node)
    graph.add_node("screen", screen_node)
    graph.add_node("news", news_node)
    graph.add_node("verdict", verdict_node)
    graph.add_edge(START, "fetch")
    graph.add_edge("fetch", "screen")
    graph.add_edge("screen", "news")
    graph.add_edge("news", "verdict")
    graph.add_edge("verdict", END)
    return graph.compile()


def run_pipeline(
    limit: int | None = None,
    tickers: list[str] | None = None,
    n: int = SCREEN_N,
    market_path: str | None = None,
    skip_fetch: bool = False,
    refresh: bool = False,
) -> PipelineState:
    """fetch -> screen -> news -> verdict into a new run folder. With skip_fetch the
    screen reads `market_path`, or the newest earlier run's market.json."""
    state: PipelineState = {"n": n, "run_dir": str(new_run_dir())}
    if skip_fetch:
        if not market_path:
            previous = latest_run_with("market.json")
            if previous is None:
                raise FileNotFoundError("--skip-fetch needs an earlier run with market.json, or --market PATH.")
            market_path = str(previous / "market.json")
        state["skip_fetch"] = True
    if limit is not None:
        state["limit"] = limit
    if tickers:
        state["tickers"] = tickers
    if market_path:
        state["market_path"] = market_path
    if refresh:
        state["refresh"] = True
    return build_graph().invoke(state)
