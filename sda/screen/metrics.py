from __future__ import annotations

from statistics import pstdev
from typing import Any

from sda.config import DcfAssumptions, VALUE_TRAP_YOY


def _growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior == 0:
        return None
    return (current - prior) / abs(prior)


def _cagr(series: list[float], periods: int = 3) -> float | None:
    if len(series) < periods + 1:
        return None
    start = series[periods]
    end = series[0]
    if start == 0:
        return None
    if start < 0 or end < 0:
        return _growth(end, start)
    return (end / start) ** (1 / periods) - 1


def net_income_growth(record: dict[str, Any]) -> dict[str, float | None | bool]:
    ni = [float(x) for x in (record.get("net_income_annual") or [])]
    yoy = _growth(ni[0], ni[1]) if len(ni) >= 2 else None
    cagr = _cagr(ni, 3)
    trap = False
    if yoy is not None and yoy <= VALUE_TRAP_YOY:
        trap = True
    if len(ni) >= 3 and ni[0] < ni[1] < ni[2] and ni[0] < 0:
        trap = True
    return {"ni_yoy": yoy, "ni_cagr_3y": cagr, "value_trap": trap}


def margin_stability(record: dict[str, Any]) -> float | None:
    """Lower standard deviation of annual EBIT/revenue is a stronger edge proxy."""
    ebit = record.get("ebit_annual") or []
    revenue = record.get("revenue_annual") or []
    n = min(len(ebit), len(revenue), 4)
    if n < 2:
        return None
    margins = []
    for i in range(n):
        if revenue[i]:
            margins.append(float(ebit[i]) / float(revenue[i]))
    if len(margins) < 2:
        return None
    return float(pstdev(margins))


def simple_dcf(record: dict[str, Any], assumptions: DcfAssumptions | None = None) -> dict[str, float | None]:
    assumptions = assumptions or DcfAssumptions()
    sector = (record.get("sector") or "").lower()
    if "financial" in sector:
        return {"dcf_fair_value": None, "dcf_yield": None, "fcf_yield": None}

    fcf_ttm = record.get("free_cashflow_ttm")
    fcf_hist = [float(x) for x in (record.get("fcf_annual") or [])]
    annual = fcf_hist[0] if fcf_hist else None
    base = annual if annual not in (None, 0) else fcf_ttm
    if (
        fcf_ttm not in (None, 0)
        and annual not in (None, 0)
        and abs(float(fcf_ttm)) < 0.3 * abs(float(annual))
    ):
        base = annual
    shares = record.get("shares")
    price = record.get("price")
    if base is None or float(base) <= 0 or not shares or not price or shares <= 0 or price <= 0:
        return {"dcf_fair_value": None, "dcf_yield": None, "fcf_yield": None}

    growth = 0.03
    if len(fcf_hist) >= 2 and fcf_hist[1] not in (0, None):
        raw = (fcf_hist[0] - fcf_hist[1]) / abs(fcf_hist[1])
        growth = min(assumptions.growth_cap, max(assumptions.growth_floor, raw))
    elif record.get("ni_yoy") is not None:
        growth = min(assumptions.growth_cap, max(assumptions.growth_floor, float(record["ni_yoy"])))

    discount = assumptions.discount_rate
    if discount <= assumptions.terminal_growth:
        return {"dcf_fair_value": None, "dcf_yield": None, "fcf_yield": None}

    total_pv = 0.0
    cash = float(base)
    for year in range(1, assumptions.years + 1):
        cash *= 1 + growth
        total_pv += cash / ((1 + discount) ** year)
    terminal_cash = cash * (1 + assumptions.terminal_growth)
    terminal_value = terminal_cash / (discount - assumptions.terminal_growth)
    total_pv += terminal_value / ((1 + discount) ** assumptions.years)

    fair = total_pv / shares
    ev = record.get("enterprise_value")
    fcf_yield = float(base) / ev if ev else float(base) / (price * shares)
    return {
        "dcf_fair_value": fair,
        "dcf_yield": fair / price - 1,
        "fcf_yield": fcf_yield,
        "dcf_growth_used": growth,
    }


def enrich_record(record: dict[str, Any]) -> dict[str, Any]:
    growth = net_income_growth(record)
    merged = {**record, **growth}
    merged["margin_stdev"] = margin_stability(record)
    merged.update(simple_dcf(merged))
    return merged
