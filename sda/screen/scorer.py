from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

from sda.screen.metrics import enrich_record
from sda.sectors import normalize_sector


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value == value


def _rel_to_median(value: float | None, med: float | None) -> float | None:
    """(value - median) / |median|: 0 at the sector median, +1 at twice it."""
    if value is None or med is None or med == 0:
        return None
    return (value - med) / abs(med)


def _clip(value: float, lo: float = -3.0, hi: float = 3.0) -> float:
    return max(lo, min(hi, value))


def attach_sector_relatives(records: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_sector: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records.values():
        by_sector[rec.get("sector") or "Unknown"].append(rec)

    sector_med: dict[str, dict[str, float | None]] = {}
    for sector, members in by_sector.items():
        pe_vals = [m["pe"] for m in members if _finite(m.get("pe")) and m["pe"] > 0]
        ps_vals = [m["ps"] for m in members if _finite(m.get("ps")) and m["ps"] > 0]
        sector_med[sector] = {
            "pe": median(pe_vals) if pe_vals else None,
            "ps": median(ps_vals) if ps_vals else None,
        }

    out = {}
    for ticker, rec in records.items():
        med = sector_med[rec.get("sector") or "Unknown"]
        pe = rec["pe"] if _finite(rec.get("pe")) else None
        ps = rec["ps"] if _finite(rec.get("ps")) else None
        out[ticker] = {
            **rec,
            "sector_pe_median": med["pe"],
            "sector_ps_median": med["ps"],
            "pe_vs_sector": _rel_to_median(pe, med["pe"]),
            "ps_vs_sector": _rel_to_median(ps, med["ps"]),
        }
    return out


def _component(value: float | None, weight: float, invert: bool = False) -> tuple[float, float]:
    if value is None:
        return 0.0, 0.0
    signed = -value if invert else value
    return weight * _clip(signed), weight


def _weighted(parts: list[tuple[float, float]], min_mass: float = 0.35) -> float | None:
    """Weighted mean over the components that have data; None when too few do."""
    mass = sum(weight for _, weight in parts)
    if mass < min_mass:
        return None
    return sum(value for value, _ in parts) / mass


def undervalued_score(rec: dict[str, Any]) -> float | None:
    if rec.get("value_trap") or rec.get("price") is None:
        return None
    margin_stdev = rec.get("margin_stdev")
    parts = [
        _component(rec.get("ni_yoy"), 0.25),
        _component(rec.get("ni_cagr_3y"), 0.15),
        _component(rec.get("pe_vs_sector"), 0.20, invert=True),
        _component(rec.get("ps_vs_sector"), 0.15, invert=True),
        _component(rec.get("dcf_yield"), 0.15),
        _component(-margin_stdev * 10 if margin_stdev is not None else None, 0.05),
        _component(rec.get("operating_margin"), 0.05),
    ]
    return _weighted(parts)


def overvalued_score(rec: dict[str, Any]) -> float | None:
    if rec.get("price") is None:
        return None
    parts = [
        _component(rec.get("pe_vs_sector"), 0.25),
        _component(rec.get("ps_vs_sector"), 0.20),
        _component(rec.get("dcf_yield"), 0.20, invert=True),
        _component(rec.get("ni_yoy"), 0.15, invert=True),
        _component(rec.get("operating_margin"), 0.10, invert=True),
        _component(rec.get("pct_1m"), 0.10),
    ]
    return _weighted(parts)


def score_universe(raw_tickers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    # Sector is normalised here too so market.json files from older runs screen correctly.
    enriched = {
        t: enrich_record({**rec, "ticker": t, "sector": normalize_sector(rec.get("sector"))})
        for t, rec in raw_tickers.items()
    }
    relative = attach_sector_relatives(enriched)
    for rec in relative.values():
        rec["undervalued_score"] = undervalued_score(rec)
        rec["overvalued_score"] = overvalued_score(rec)
        rec["abs_pct_1w"] = abs(rec["pct_1w"]) if _finite(rec.get("pct_1w")) else None
        rec["abs_pct_1m"] = abs(rec["pct_1m"]) if _finite(rec.get("pct_1m")) else None
    return relative


def top_n(records: dict[str, dict[str, Any]], key: str, n: int) -> list[dict[str, Any]]:
    rows = [rec for rec in records.values() if _finite(rec.get(key))]
    rows.sort(key=lambda r: r[key], reverse=True)
    return rows[:n]


EXPORT_FIELDS = [
    "ticker",
    "name",
    "sector",
    "price",
    "price_as_of",
    "pe",
    "ps",
    "pe_vs_sector",
    "ps_vs_sector",
    "ni_yoy",
    "ni_cagr_3y",
    "value_trap",
    "dcf_fair_value",
    "dcf_yield",
    "fcf_yield",
    "dcf_growth_used",
    "operating_margin",
    "roe",
    "margin_stdev",
    "pct_1w",
    "pct_1m",
    "undervalued_score",
    "overvalued_score",
]


def slim(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in EXPORT_FIELDS}
