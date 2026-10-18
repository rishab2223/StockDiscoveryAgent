"""One sector taxonomy for every record.

The S&P 500 list uses GICS names; Yahoo's `.info` uses its own ("Technology",
"Healthcare", ...). Mixing them splits the sector medians the screen relies on,
so everything is mapped onto GICS.
"""

from __future__ import annotations

GICS_SECTORS = (
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
)

_YAHOO_TO_GICS = {
    "technology": "Information Technology",
    "healthcare": "Health Care",
    "financial services": "Financials",
    "financial": "Financials",
    "consumer cyclical": "Consumer Discretionary",
    "consumer defensive": "Consumer Staples",
    "basic materials": "Materials",
}
_GICS_BY_LOWER = {name.lower(): name for name in GICS_SECTORS}


def normalize_sector(raw: str | None) -> str:
    key = (raw or "").strip().lower()
    if not key:
        return "Unknown"
    return _GICS_BY_LOWER.get(key) or _YAHOO_TO_GICS.get(key) or raw.strip()
