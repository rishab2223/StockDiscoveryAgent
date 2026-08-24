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

DCF_DISCOUNT_RATE = 0.10
DCF_TERMINAL_GROWTH = 0.025
DCF_YEARS = 5
DCF_GROWTH_CAP = 0.15
DCF_GROWTH_FLOOR = -0.05

VALUE_TRAP_YOY = -0.25
NEWS_LOOKBACK_DAYS = 7
FUNDAMENTAL_WORKERS = 8

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LLM_NEWS_CLASSIFIER = os.getenv("SMA_LLM_NEWS_CLASSIFIER", "0").lower() in {
    "1",
    "true",
    "yes",
}


@dataclass(frozen=True)
class DcfAssumptions:
    discount_rate: float = DCF_DISCOUNT_RATE
    terminal_growth: float = DCF_TERMINAL_GROWTH
    years: int = DCF_YEARS
    growth_cap: float = DCF_GROWTH_CAP
    growth_floor: float = DCF_GROWTH_FLOOR


def ensure_dirs() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
