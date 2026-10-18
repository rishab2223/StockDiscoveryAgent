from sda import config
from sda.llm import claude
from sda.news.classifier import NewsDecision, classify_ambiguous


def test_classifier_off_drops_everything_with_reason():
    items = [{"ticker": "A", "title": "x"}]
    assert classify_ambiguous([]) == []
    out = classify_ambiguous(items)
    assert out[0]["final_label"] == "drop" and "disabled" in out[0]["llm_reason"]


def test_classifier_openai_without_key(monkeypatch):
    monkeypatch.setattr(config, "LLM_NEWS_CLASSIFIER", True)
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    out = classify_ambiguous([{"ticker": "A", "title": "x"}])
    assert out[0]["final_label"] == "drop" and out[0]["llm_reason"] == "no OPENAI_API_KEY"


def test_classifier_claude_keeps_order_and_drops_failed_calls(monkeypatch):
    monkeypatch.setattr(config, "LLM_NEWS_CLASSIFIER", True)
    seen = {}

    def fake_batch(system, prompts, schema):
        seen["prompts"], seen["schema"] = prompts, schema
        return [NewsDecision(decision="keep", reason="earnings"), RuntimeError("timeout")]

    monkeypatch.setattr(claude, "structured_batch", fake_batch)
    items = [{"ticker": "A", "title": "A beats", "publisher": "PR"}, {"ticker": "B", "title": "B?", "summary": "s"}]
    out = classify_ambiguous(items)
    assert [(o["ticker"], o["final_label"], o["llm_reason"]) for o in out] == [
        ("A", "keep", "earnings"),
        ("B", "drop", "classifier failed"),
    ]
    assert seen["schema"] is NewsDecision
    assert seen["prompts"][0] == "Ticker: A\nHeadline: A beats\nSummary: \nPublisher: PR"
