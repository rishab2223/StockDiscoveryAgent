from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from sda import config

SYSTEM_PROMPT = (
    "You classify a stock headline. KEEP only company-originated or factual "
    "corporate events (earnings, products, filings, M&A, regulation, leadership). "
    "DROP analyst recommendations, price targets, personal opinion, and generic market color."
)
USER_PROMPT = "Ticker: {ticker}\nHeadline: {title}\nSummary: {summary}\nPublisher: {publisher}"


class NewsDecision(BaseModel):
    decision: Literal["keep", "drop"]
    reason: str = Field(description="Short reason using only the headline text")


def _dropped(items: list[dict[str, Any]], reason: str) -> list[dict[str, Any]]:
    return [{**item, "final_label": "drop", "llm_reason": reason} for item in items]


def _openai_batch(rows: list[dict[str, Any]]) -> list[NewsDecision]:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", USER_PROMPT)])
    chain = prompt | ChatOpenAI(model=config.OPENAI_MODEL, temperature=0).with_structured_output(NewsDecision)
    return chain.batch(rows, config={"max_concurrency": config.LLM_CONCURRENCY})


def classify_ambiguous(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """LLM keep/drop for leftovers (LLM_PROVIDER decides which model).
    Drops everything unless SMA_LLM_NEWS_CLASSIFIER is on."""
    if not items:
        return []
    if not config.LLM_NEWS_CLASSIFIER:
        return _dropped(items, "classifier disabled; leftover dropped")

    rows = [
        {
            "ticker": item.get("ticker"),
            "title": item.get("title"),
            "summary": item.get("summary") or "",
            "publisher": item.get("publisher") or "",
        }
        for item in items
    ]
    if config.LLM_PROVIDER == "claude":
        from sda.llm.claude import structured_batch

        decisions: list[Any] = structured_batch(SYSTEM_PROMPT, [USER_PROMPT.format(**row) for row in rows], NewsDecision)
    else:
        if not os.getenv("OPENAI_API_KEY"):
            return _dropped(items, "no OPENAI_API_KEY")
        try:
            decisions = _openai_batch(rows)
        except Exception:
            return _dropped(items, "classifier failed")

    return [
        {**item, "final_label": "drop", "llm_reason": "classifier failed"}
        if isinstance(decision, Exception)
        else {**item, "final_label": decision.decision, "llm_reason": decision.reason}
        for item, decision in zip(items, decisions)
    ]
