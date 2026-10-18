from sda import config
from sda.news.classifier import classify_ambiguous


def test_classifier_off_drops_everything_with_reason():
    items = [{"ticker": "A", "title": "x"}]
    assert classify_ambiguous([]) == []
    out = classify_ambiguous(items)
    assert out[0]["final_label"] == "drop" and "disabled" in out[0]["llm_reason"]


def test_classifier_on_without_key(monkeypatch):
    monkeypatch.setattr(config, "LLM_NEWS_CLASSIFIER", True)
    out = classify_ambiguous([{"ticker": "A", "title": "x"}])
    assert out[0]["final_label"] == "drop" and out[0]["llm_reason"] == "no OPENAI_API_KEY"
