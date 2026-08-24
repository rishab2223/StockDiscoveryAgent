from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

from sma.screen.metrics import enrich_record


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and value == value


def _z(value: float | None, med: float | None) -> float | None:
    if value is None or med is None or med == 0:
        return None
    return (value - med) / abs(med)


def _clip(value: float, lo: float = -3.0, hi: float = 3.0) -> float:
    return max(lo, min(hi, value))


def attach_sector_relatives(records: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_sector: dict[str, list[str]] = defaultdict(list)
    for ticker, rec in records.items():
        by_sector[rec.get("sector") or "Unknown"].append(ticker)

    sector_med: dict[str, dict[str, float]] = {}
    for sector, members in by_sector.items():
        pe_vals = [records[t]["pe"] for t in members if _finite(records[t].get("pe")) and records[t]["pe"] > 0]
        ps_vals = [records[t]["ps"] for t in members if _finite(records[t].get("ps")) and records[t]["ps"] > 0]
        sector_med[sector] = {
            "pe": median(pe_vals) if pe_vals else None,
            "ps": median(ps_vals) if ps_vals else None,
        }

    out = {}
    for ticker, rec in records.items():
        sector = rec.get("sector") or "Unknown"
        med = sector_med.get(sector, {})
        row = {
            **rec,
            "sector_pe_median": med.get("pe"),
            "sector_ps_median": med.get("ps"),
            "pe_vs_sector": _z(rec.get("pe") if _finite(rec.get("pe")) else None, med.get("pe")),
            "ps_vs_sector": _z(rec.get("ps") if _finite(rec.get("ps")) else None, med.get("ps")),
        }
        out[ticker] = row
    return out


def _component(value: float | None, weight: float, invert: bool = False) -> tuple[float, float]:
    if value is None:
        return 0.0, 0.0
    signed = -value if invert else value
    return weight * _clip(signed), weight


def undervalued_score(rec: dict[str, Any]) -> float | None:
    if rec.get("value_trap"):
        return None
    if rec.get("price") is None:
        return None
    parts = [
        _component(rec.get("ni_yoy"), 0.25),
        _component(rec.get("ni_cagr_3y"), 0.15),
        _component(rec.get("pe_vs_sector"), 0.20, invert=True),
        _component(rec.get("ps_vs_sector"), 0.15, invert=True),
        _component(rec.get("dcf_yield"), 0.15),
        _component(
            -rec["margin_stdev"] * 10 if rec.get("margin_stdev") is not None else None,
            0.05,
        ),
        _component(rec.get("operating_margin"), 0.05),
    ]
    weighted = sum(p[0] for p in parts)
    mass = sum(p[1] for p in parts)
    if mass < 0.35:
        return None
    return weighted / mass


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
    weighted = sum(p[0] for p in parts)
    mass = sum(p[1] for p in parts)
    if mass < 0.35:
        return None
    return weighted / mass


def score_universe(raw_tickers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    enriched = {t: enrich_record(dict(rec, ticker=t)) for t, rec in raw_tickers.items()}
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
