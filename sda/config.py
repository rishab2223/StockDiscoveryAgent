from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "cache"
OUTPUT_DIR = ROOT / "output"

SCREEN_N = 20
HISTORY_PERIOD = "6mo"
TRADING_DAYS_1W = 5
TRADING_DAYS_1M = 21

VALUE_TRAP_YOY = -0.25
NEWS_LOOKBACK_DAYS = 7
NEWS_COUNT = 25
FUNDAMENTAL_WORKERS = 8

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LLM_NEWS_CLASSIFIER = os.getenv("SMA_LLM_NEWS_CLASSIFIER", "0").lower() in {
    "1",
    "true",
    "yes",
}


@dataclass(frozen=True)
class DcfAssumptions:
    discount_rate: float = 0.10
    terminal_growth: float = 0.025
    years: int = 5
    growth_cap: float = 0.15
    growth_floor: float = -0.05


def ensure_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
