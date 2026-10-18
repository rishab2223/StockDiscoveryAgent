import json

import pytest

from sda import cli
from sda.cli import _tickers, build_parser, main


def test_tickers_parsing():
    assert _tickers(None) is None and _tickers("") is None
    assert _tickers(" aapl, msft ,,") == ["AAPL", "MSFT"]


def test_parser_defaults_and_flags():
    args = build_parser().parse_args(["run", "--skip-fetch", "--market", "m.json", "--n", "5", "--refresh"])
    assert args.skip_fetch and args.market_path == "m.json" and args.n == 5 and args.refresh
    assert build_parser().parse_args(["screen"]).n == 20
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["screen", "--cache", "x"])


def test_main_dispatches_and_prints_summaries(monkeypatch, capsys):
    import sda.fetch.agent
    import sda.graph.pipeline
    import sda.news.agent
    import sda.screen.agent
    import sda.verdict.agent

    seen = {}

    def record(name, payload):
        def fake(**kw):
            seen[name] = kw
            return payload

        return fake

    monkeypatch.setattr(
        sda.fetch.agent,
        "fetch_market_data",
        record("fetch", {"run_dir": "r", "market_path": "m", "ticker_count": 2, "fundamentals_cached": 1, "errors": [1]}),
    )
    monkeypatch.setattr(
        sda.screen.agent, "run_screen", lambda **kw: {"run_dir": "r", "screen_path": "s", "lists": {"undervalued": [1, 2], "overvalued": []}}
    )
    monkeypatch.setattr(
        sda.news.agent, "analyze_news", lambda **kw: {"run_dir": "r", "news_path": "n", "tickers": {"A": {"kept": [1]}, "B": {"kept": []}}}
    )
    monkeypatch.setattr(sda.verdict.agent, "write_verdicts", lambda **kw: {"run_dir": "r", "verdicts_path": "v", "verdicts": [1]})
    monkeypatch.setattr(sda.graph.pipeline, "run_pipeline", record("run", {"run_dir": "r", "market_path": "m"}))

    assert main(["fetch", "--limit", "3", "--tickers", "a,b", "--refresh"]) == 0
    assert seen["fetch"] == {"limit": 3, "tickers": ["A", "B"], "refresh": True}
    assert json.loads(capsys.readouterr().out) == {"run_dir": "r", "market_path": "m", "ticker_count": 2, "fundamentals_cached": 1, "errors": 1}

    assert main(["screen", "--n", "2"]) == 0
    assert json.loads(capsys.readouterr().out)["counts"] == {"undervalued": 2, "overvalued": 0}

    assert main(["news"]) == 0
    assert json.loads(capsys.readouterr().out) == {"run_dir": "r", "news_path": "n", "tickers": 2, "kept_items": 1}

    assert main(["verdict"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1

    assert main(["run", "--skip-fetch", "--n", "4"]) == 0
    assert seen["run"] == {"limit": None, "tickers": None, "n": 4, "market_path": None, "skip_fetch": True, "refresh": False}
    out = json.loads(capsys.readouterr().out)
    assert out["market_path"] == "m" and out["verdicts_path"] is None


def test_module_entry_point():
    assert cli.main is not None
