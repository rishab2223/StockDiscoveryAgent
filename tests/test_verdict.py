import json

import pytest

from sda import config
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


def test_run_verdicts_requires_key_and_preserves_order(monkeypatch):
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
