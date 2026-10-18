from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from sda import config

METRIC_KEYS = [
    "price",
    "price_as_of",
    "sector",
    "pe",
    "ps",
    "pe_vs_sector",
    "ps_vs_sector",
    "ni_yoy",
    "ni_cagr_3y",
    "value_trap",
    "dcf_yield",
    "dcf_fair_value",
    "pct_1w",
    "pct_1m",
    "undervalued_score",
    "overvalued_score",
]


class TickerVerdict(BaseModel):
    # Only the model-written text is requested; ticker/buckets/dates are attached locally.
    conclusion: str = Field(
        description="Free-form conclusion using only the provided metrics and news. "
        "If news is thin, say so. Do not invent facts or give a buy/sell as if it were advice."
    )


def _news_block(kept: list[dict[str, Any]]) -> str:
    if not kept:
        return "No usable company-originated news in the lookback window."
    lines = []
    for item in kept[:12]:
        when = item.get("published_at") or "unknown date"
        lines.append(f"- [{when}] {item.get('title')} ({item.get('publisher')})")
        if item.get("summary"):
            lines.append(f"  {item['summary'][:280]}")
    return "\n".join(lines)


def _metrics_block(row: dict[str, Any] | None) -> str:
    if not row:
        return "No screen metrics attached."
    return "\n".join(f"{k}: {row.get(k)}" for k in METRIC_KEYS)


SYSTEM_PROMPT = (
    "You are a research assistant. Combine the screening metrics and the cleaned "
    "company news. Use only those facts. Ignore leftover opinion or recommendations. "
    "Write a concise free-form conclusion (the verdict). If news is thin, say so. "
    "Do not invent events. This is not investment advice."
)
USER_PROMPT = (
    "Ticker: {ticker}\nBuckets: {buckets}\nAs of: {as_of}\n\n"
    "Screen metrics:\n{metrics}\n\nCleaned news:\n{news}"
)


def build_verdict_chain():
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    prompt = ChatPromptTemplate.from_messages([("system", SYSTEM_PROMPT), ("human", USER_PROMPT)])
    model = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0.2).with_structured_output(TickerVerdict)
    return prompt | model


def _ask_model(batch: list[dict[str, Any]]) -> list[TickerVerdict | Exception]:
    if config.LLM_PROVIDER == "claude":
        from sda.llm.claude import structured_batch

        return structured_batch(SYSTEM_PROMPT, [USER_PROMPT.format(**row) for row in batch], TickerVerdict)
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai.")
    return build_verdict_chain().batch(batch, config={"max_concurrency": config.LLM_CONCURRENCY})


def run_verdicts(
    news_payload: dict[str, Any],
    screen_rows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """One verdict per news ticker, in order. A failed call leaves `conclusion`
    empty and records `error`; if every call fails the step raises instead of
    writing an empty watchlist."""
    tickers: dict[str, dict[str, Any]] = news_payload.get("tickers") or {}
    if not tickers:
        return []
    as_of = news_payload.get("screen_as_of") or news_payload.get("as_of")
    batch = [
        {
            "ticker": ticker,
            "buckets": ", ".join(blob.get("buckets") or []),
            "as_of": as_of,
            "metrics": _metrics_block(screen_rows.get(ticker)),
            "news": _news_block(blob.get("kept") or []),
        }
        for ticker, blob in tickers.items()
    ]
    results = _ask_model(batch)
    failures = [result for result in results if isinstance(result, Exception)]
    if failures and len(failures) == len(results):
        raise RuntimeError(f"Every verdict call failed; first error: {failures[0]}") from failures[0]

    verdicts = []
    for (ticker, blob), result in zip(tickers.items(), results):
        verdict = {
            "ticker": ticker,
            "buckets": blob.get("buckets") or [],
            "as_of": as_of,
            "kept_news_count": len(blob.get("kept") or []),
            "conclusion": None if isinstance(result, Exception) else result.conclusion,
        }
        if isinstance(result, Exception):
            verdict["error"] = str(result)[:300]
        verdicts.append(verdict)
    return verdicts
