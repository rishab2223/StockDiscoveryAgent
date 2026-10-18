from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from sda import config


class NewsDecision(BaseModel):
    decision: Literal["keep", "drop"]
    reason: str = Field(description="Short reason using only the headline text")


def _dropped(items: list[dict[str, Any]], reason: str) -> list[dict[str, Any]]:
    return [{**item, "final_label": "drop", "llm_reason": reason} for item in items]


def classify_ambiguous(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """GPT keep/drop for leftovers. Drops everything unless SMA_LLM_NEWS_CLASSIFIER is on."""
    if not items:
        return []
    if not config.LLM_NEWS_CLASSIFIER:
        return _dropped(items, "classifier disabled; leftover dropped")
    if not os.getenv("OPENAI_API_KEY"):
        return _dropped(items, "no OPENAI_API_KEY")

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
    chain = prompt | ChatOpenAI(model=config.OPENAI_MODEL, temperature=0).with_structured_output(NewsDecision)

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
        decisions = chain.batch(batch_in, config={"max_concurrency": config.LLM_CONCURRENCY})
    except Exception:
        return _dropped(items, "classifier failed")

    return [
        {**item, "final_label": decision.decision, "llm_reason": decision.reason}
        for item, decision in zip(items, decisions)
    ]
