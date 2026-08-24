from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from sda.config import LLM_NEWS_CLASSIFIER, OPENAI_MODEL


class NewsDecision(BaseModel):
    decision: Literal["keep", "drop"]
    reason: str = Field(description="Short reason using only the headline text")


def classify_ambiguous(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """GPT keep/drop for leftovers. No-ops unless SMA_LLM_NEWS_CLASSIFIER is enabled."""
    if not items or not LLM_NEWS_CLASSIFIER:
        return [{**item, "final_label": "drop", "llm_reason": "classifier disabled; leftover dropped"} for item in items]

    import os

    if not os.getenv("OPENAI_API_KEY"):
        return [{**item, "final_label": "drop", "llm_reason": "no OPENAI_API_KEY"} for item in items]

    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You classify a stock headline. KEEP only company-originated or factual "
                "corporate events (earnings, products, filings, M&A, regulation, leadership). "
                "DROP analyst recommendations, price targets, personal opinion, and generic market color.",
            ),
            ("human", "Ticker: {ticker}\nHeadline: {title}\nSummary: {summary}\nPublisher: {publisher}"),
        ]
    )
    model = ChatOpenAI(model=OPENAI_MODEL, temperature=0).with_structured_output(NewsDecision)
    chain = prompt | model

    batch_in = [
        {
            "ticker": item.get("ticker"),
            "title": item.get("title"),
            "summary": item.get("summary") or "",
            "publisher": item.get("publisher") or "",
        }
        for item in items
    ]
    try:
        decisions = chain.batch(batch_in, config={"max_concurrency": 4})
    except Exception:
        return [{**item, "final_label": "drop", "llm_reason": "classifier failed"} for item in items]

    out = []
    for item, decision in zip(items, decisions):
        out.append(
            {
                **item,
                "final_label": decision.decision,
                "llm_reason": decision.reason,
            }
        )
    return out
