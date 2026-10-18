import json

import pytest

from sda import config
from sda.llm import claude
from sda.verdict import chain as chain_mod
from sda.verdict.agent import write_verdicts, write_verdicts_markdown
from sda.verdict.chain import TickerVerdict, _metrics_block, _news_block, run_verdicts
from tests.conftest import sample_screen, write_run


class FakeChain:
    def __init__(self):
        self.batches = []

    def batch(self, batch, config=None):
        self.batches.append((batch, config))
        return [TickerVerdict(conclusion=f"verdict for {row['ticker']}") for row in batch]


def _news_payload():
    return {
        "as_of": "2026-10-02T00:00:00+00:00",
        "screen_as_of": "2026-10-01T00:00:00+00:00",
        "tickers": {
            "AAA": {"buckets": ["undervalued", "dev_1w"], "kept": [{"title": "t", "publisher": "p", "summary": "s" * 300, "published_at": "2026-10-01"}]},
            "BBB": {"buckets": ["undervalued"], "kept": []},
        },
    }


def test_prompt_blocks():
    assert _news_block([]).startswith("No usable")
    block = _news_block(_news_payload()["tickers"]["AAA"]["kept"])
    assert "- [2026-10-01] t (p)" in block and len(block.splitlines()[1].strip()) == 280
    assert _metrics_block(None) == "No screen metrics attached."
    assert "pe: 6\n" in _metrics_block({"pe": 6}) + "\n" and "overvalued_score: None" in _metrics_block({"pe": 6})


def test_claude_provider_formats_prompts_and_keeps_order(monkeypatch):
    calls = []

    def fake_batch(system, prompts, schema):
        calls.append((system, prompts, schema))
        return [TickerVerdict(conclusion=f"claude {i}") for i in range(len(prompts))]

    monkeypatch.setattr(claude, "structured_batch", fake_batch)
    out = run_verdicts(_news_payload(), {"AAA": {"pe": 6}})
    assert [(v["ticker"], v["conclusion"]) for v in out] == [("AAA", "claude 0"), ("BBB", "claude 1")]
    assert "error" not in out[0]
    system, prompts, schema = calls[0]
    assert system == chain_mod.SYSTEM_PROMPT and schema is TickerVerdict
    assert prompts[0].startswith("Ticker: AAA\nBuckets: undervalued, dev_1w\nAs of: 2026-10-01")
    assert "pe: 6" in prompts[0] and "No usable" in prompts[1]


def test_failed_calls_are_recorded_and_total_failure_raises(monkeypatch):
    monkeypatch.setattr(
        claude, "structured_batch", lambda system, prompts, schema: [TickerVerdict(conclusion="ok"), RuntimeError("timed out")]
    )
    out = run_verdicts(_news_payload(), {})
    assert out[0]["conclusion"] == "ok" and out[1]["conclusion"] is None and out[1]["error"] == "timed out"

    monkeypatch.setattr(claude, "structured_batch", lambda system, prompts, schema: [RuntimeError("logged out")] * len(prompts))
    with pytest.raises(RuntimeError, match="Every verdict call failed; first error: logged out"):
        run_verdicts(_news_payload(), {})


def test_openai_provider_requires_key_and_preserves_order(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    with pytest.raises(RuntimeError):
        run_verdicts(_news_payload(), {})
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    fake = FakeChain()
    monkeypatch.setattr(chain_mod, "build_verdict_chain", lambda: fake)

    out = run_verdicts(_news_payload(), {"AAA": {"pe": 6}})
    assert [v["ticker"] for v in out] == ["AAA", "BBB"]
    assert out[0] == {
        "ticker": "AAA",
        "buckets": ["undervalued", "dev_1w"],
        "as_of": "2026-10-01T00:00:00+00:00",
        "kept_news_count": 1,
        "conclusion": "verdict for AAA",
    }
    batch, cfg = fake.batches[0]
    assert batch[0]["buckets"] == "undervalued, dev_1w" and "pe: 6" in batch[0]["metrics"]
    assert batch[1]["news"].startswith("No usable") and batch[1]["metrics"] == "No screen metrics attached."
    assert cfg == {"max_concurrency": config.LLM_CONCURRENCY}
    assert run_verdicts({"tickers": {}}, {}) == []


def test_write_verdicts_end_to_end(monkeypatch):
    run_dir = write_run(config.OUTPUT_DIR / "2026-10-01_000000Z", screen=sample_screen(), news_clean=_news_payload())
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(chain_mod, "build_verdict_chain", lambda: FakeChain())

    payload = write_verdicts()
    assert payload["run_dir"] == str(run_dir)
    on_disk = json.loads((run_dir / "verdicts.json").read_text(encoding="utf-8"))
    assert [v["ticker"] for v in on_disk["verdicts"]] == ["AAA", "BBB"]
    md = (run_dir / "verdicts.md").read_text(encoding="utf-8")
    assert "## AAA" in md and "- Buckets: undervalued, dev_1w" in md and "verdict for BBB" in md


def test_write_verdicts_needs_inputs(tmp_path):
    write_run(config.OUTPUT_DIR / "2026-10-01_000000Z", screen=sample_screen())
    with pytest.raises(FileNotFoundError, match="news_clean.json"):
        write_verdicts()
    with pytest.raises(FileNotFoundError, match="screen.json"):
        write_verdicts(news_path=str(write_run(tmp_path / "x", news_clean=_news_payload()) / "news_clean.json"))


def test_markdown_handles_empty_fields(tmp_path):
    path = write_verdicts_markdown(tmp_path / "v.md", "now", [{"ticker": "Z"}])
    text = path.read_text(encoding="utf-8")
    assert "- Buckets: n/a" in text and "_No conclusion._" in text
