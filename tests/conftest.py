from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sda import config


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Every test gets its own output/ and cache/ and no live LLM."""
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(config, "LLM_NEWS_CLASSIFIER", False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return tmp_path


def make_record(**overrides: Any) -> dict[str, Any]:
    base = {
        "name": "Cheap Co",
        "sector": "Energy",
        "price": 20.0,
        "price_as_of": "2026-08-21",
        "shares": 1_000_000,
        "free_cashflow_ttm": 5_000_000,
        "fcf_annual": [5_000_000, 4_000_000],
        "net_income_annual": [4_000_000, 3_000_000, 2_500_000, 2_000_000],
        "ebit_annual": [5_000_000, 4_000_000, 3_500_000],
        "revenue_annual": [20_000_000, 16_000_000, 14_000_000],
        "enterprise_value": 25_000_000,
        "pe": 6,
        "ps": 0.8,
        "operating_margin": 0.25,
        "pct_1w": 0.01,
        "pct_1m": 0.02,
    }
    return {**base, **overrides}


def write_run(run_dir: Path, **files: Any) -> Path:
    """Create a run folder holding the given JSON files (name without .json)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        (run_dir / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    return run_dir


def sample_screen() -> dict[str, Any]:
    return {
        "as_of": "2026-10-01T00:00:00+00:00",
        "n": 2,
        "lists": {
            "undervalued": [
                {"ticker": "AAA", "name": "Alpha Inc.", "price": 10.0},
                {"ticker": "BBB", "name": "Beta Corp", "price": 20.0},
            ],
            "dev_1w": [{"ticker": "AAA", "name": "Alpha Inc.", "price": 10.0}],
            "overvalued": [],
            "dev_1m": [],
        },
    }
