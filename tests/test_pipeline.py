import json
from pathlib import Path

import pytest

from sda import config
from sda.graph import pipeline
from sda.graph.pipeline import build_graph, run_pipeline
from tests.conftest import write_run


def _install_fakes(monkeypatch, calls):
    def fetch(limit=None, tickers=None, run_dir=None, refresh=False):
        calls.append(("fetch", limit, tickers, refresh))
        path = Path(run_dir) / "market.json"
        path.write_text("{}")
        return {"market_path": str(path), "run_dir": run_dir}

    def screen(n, market_path=None, run_dir=None):
        calls.append(("screen", n, market_path))
        path = Path(run_dir) / "screen.json"
        path.write_text("{}")
        return {"screen_path": str(path), "run_dir": run_dir}

    def news(screen_path=None, run_dir=None):
        calls.append(("news", screen_path))
        path = Path(run_dir) / "news_clean.json"
        path.write_text("{}")
        return {"news_path": str(path), "run_dir": run_dir}

    def verdict(news_path=None, screen_path=None, run_dir=None):
        calls.append(("verdict", news_path, screen_path))
        path = Path(run_dir) / "verdicts.json"
        path.write_text("{}")
        return {"verdicts_path": str(path), "markdown_path": str(path.with_suffix(".md")), "run_dir": run_dir}

    monkeypatch.setattr(pipeline, "fetch_market_data", fetch)
    monkeypatch.setattr(pipeline, "run_screen", screen)
    monkeypatch.setattr(pipeline, "analyze_news", news)
    monkeypatch.setattr(pipeline, "write_verdicts", verdict)


def test_graph_runs_all_four_steps_in_one_run_dir(monkeypatch):
    calls = []
    _install_fakes(monkeypatch, calls)
    state = run_pipeline(limit=5, tickers=["A"], n=3, refresh=True)
    run_dir = Path(state["run_dir"])
    assert run_dir.parent == config.OUTPUT_DIR
    assert [c[0] for c in calls] == ["fetch", "screen", "news", "verdict"]
    assert calls[0] == ("fetch", 5, ["A"], True)
    assert calls[1] == ("screen", 3, str(run_dir / "market.json"))
    assert state["screen_path"] == str(run_dir / "screen.json")
    assert state["verdicts_path"] == str(run_dir / "verdicts.json") and state["markdown_path"].endswith(".md")
    assert {p.name for p in run_dir.iterdir()} == {"market.json", "screen.json", "news_clean.json", "verdicts.json"}


def test_skip_fetch_reuses_newest_market_json(monkeypatch):
    calls = []
    _install_fakes(monkeypatch, calls)
    with pytest.raises(FileNotFoundError):
        run_pipeline(skip_fetch=True)

    old = write_run(config.OUTPUT_DIR / "2026-01-01_000000Z", market={"tickers": {}})
    state = run_pipeline(skip_fetch=True, n=2)
    assert state["market_path"] == str(old / "market.json")
    assert [c[0] for c in calls] == ["screen", "news", "verdict"]
    assert Path(state["run_dir"]) != old and Path(state["screen_path"]).parent == Path(state["run_dir"])

    calls.clear()
    state = run_pipeline(skip_fetch=True, market_path="explicit.json")
    assert calls[0] == ("screen", 20, "explicit.json")


def test_graph_shape():
    graph = build_graph()
    nodes = graph.get_graph().nodes
    assert {"fetch", "screen", "news", "verdict"} <= set(nodes)
    assert json.dumps(sorted(nodes))  # serialisable names
