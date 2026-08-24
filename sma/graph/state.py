from __future__ import annotations

from typing import TypedDict


class PipelineState(TypedDict, total=False):
    limit: int | None
    tickers: list[str] | None
    n: int
    skip_fetch: bool
    run_dir: str
    cache_path: str
    screen_path: str
    news_path: str
    verdicts_path: str
    markdown_path: str
