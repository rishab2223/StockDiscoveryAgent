from sda.config import DcfAssumptions
from sda.screen.metrics import _cagr, enrich_record, margin_stability, net_income_growth, simple_dcf
from tests.conftest import make_record


def test_value_trap_flags_sharp_yoy_decline():
    record = make_record(net_income_annual=[10_000_000, 20_000_000, 25_000_000])
    enriched = enrich_record(record)
    assert enriched["value_trap"] is True
    assert enriched["ni_yoy"] < 0
    # Trap or not, the DCF still runs on positive free cash flow.
    assert enriched["dcf_fair_value"] is not None
    assert enriched["dcf_yield"] is not None


def test_value_trap_flags_three_year_decline_into_losses():
    growth = net_income_growth({"net_income_annual": [-1, 2, 3]})
    assert growth["value_trap"] is True
    assert net_income_growth({"net_income_annual": [3, 2, 1]})["value_trap"] is False
    assert net_income_growth({"net_income_annual": []}) == {"ni_yoy": None, "ni_cagr_3y": None, "value_trap": False}


def test_cagr_handles_short_and_negative_series():
    assert _cagr([8, 4, 2, 1]) == 1.0
    assert _cagr([1, 2]) is None
    assert _cagr([2, 1, 1, 0]) is None
    assert _cagr([-2, 1, 1, -4]) == 0.5  # falls back to simple growth when signs flip


def test_margin_stability_needs_two_years():
    assert margin_stability({"ebit_annual": [1], "revenue_annual": [10]}) is None
    assert margin_stability({"ebit_annual": [1, 1], "revenue_annual": [10, 10]}) == 0.0
    assert margin_stability({"ebit_annual": [2, 1], "revenue_annual": [10, 10]}) > 0


def test_dcf_skips_financials_and_non_positive_cash():
    empty = {"dcf_fair_value": None, "dcf_yield": None, "fcf_yield": None}
    assert simple_dcf(make_record(sector="Financials")) == empty
    assert simple_dcf(make_record(fcf_annual=[-5, 1], free_cashflow_ttm=-5)) == empty
    assert simple_dcf(make_record(shares=None)) == empty


def test_dcf_clamps_growth_and_prefers_annual_fcf():
    record = make_record(fcf_annual=[10_000_000, 1_000_000])  # +900% YoY -> capped
    assert simple_dcf(record)["dcf_growth_used"] == DcfAssumptions().growth_cap
    record = make_record(fcf_annual=[1_000_000, 10_000_000])  # -90% -> floored
    assert simple_dcf(record)["dcf_growth_used"] == DcfAssumptions().growth_floor
    # A TTM figure far below the annual one is treated as noise.
    record = make_record(fcf_annual=[5_000_000, 5_000_000], free_cashflow_ttm=100)
    assert simple_dcf(record)["fcf_yield"] == 5_000_000 / 25_000_000


def test_dcf_yield_is_relative_to_price():
    out = simple_dcf(make_record(), DcfAssumptions(discount_rate=0.08))
    assert out["dcf_yield"] == out["dcf_fair_value"] / 20.0 - 1
    assert simple_dcf(make_record(), DcfAssumptions(discount_rate=0.02))["dcf_fair_value"] is None
