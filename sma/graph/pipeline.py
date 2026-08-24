from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from sma.config import SCREEN_N
from sma.fetch.agent import fetch_market_data
from sma.graph.state import PipelineState
from sma.news.agent import analyze_news
from sma.run_dir import new_run_dir
from sma.screen.agent import run_screen
from sma.verdict.agent import write_verdicts


def fetch_node(state: PipelineState) -> dict[str, Any]:
    if state.get("skip_fetch") and state.get("cache_path"):
        return {}
    payload = fetch_market_data(
        limit=state.get("limit"),
        tickers=state.get("tickers"),
        run_dir=state.get("run_dir"),
    )
    return {"cache_path": payload["cache_path"], "run_dir": payload["run_dir"]}


def screen_node(state: PipelineState) -> dict[str, Any]:
    payload = run_screen(
        n=state.get("n") or SCREEN_N,
        cache_path=state.get("cache_path"),
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
    cache_path: str | None = None,
    skip_fetch: bool = False,
) -> PipelineState:
    app = build_graph()
    state: PipelineState = {"n": n, "run_dir": str(new_run_dir())}
    if limit is not None:
        state["limit"] = limit
    if tickers:
        state["tickers"] = tickers
    if cache_path:
        state["cache_path"] = cache_path
    if skip_fetch:
        state["skip_fetch"] = True
    return app.invoke(state)
