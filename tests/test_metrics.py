from sma.screen.metrics import enrich_record, simple_dcf
from sma.screen.scorer import score_universe, top_n


def test_value_trap_and_dcf():
    record = {
        "price": 50.0,
        "shares": 10_000_000,
        "free_cashflow_ttm": 80_000_000,
        "fcf_annual": [80_000_000, 70_000_000],
        "net_income_annual": [10_000_000, 20_000_000, 25_000_000],
        "enterprise_value": 600_000_000,
        "sector": "Tech",
        "pe": 8,
        "ps": 1.2,
        "operating_margin": 0.2,
        "pct_1w": -0.02,
        "pct_1m": -0.04,
    }
    enriched = enrich_record(record)
    assert enriched["value_trap"] is True
    assert enriched["ni_yoy"] is not None and enriched["ni_yoy"] < 0
    dcf = simple_dcf(enriched)
    assert dcf["dcf_fair_value"] is not None
    assert dcf["dcf_yield"] is not None


def test_screen_ranks_four_lists():
    cheap = {
        "price": 20,
        "price_as_of": "2026-08-21",
        "shares": 1_000_000,
        "free_cashflow_ttm": 5_000_000,
        "fcf_annual": [5_000_000, 4_000_000],
        "net_income_annual": [4_000_000, 3_000_000, 2_500_000, 2_000_000],
        "enterprise_value": 25_000_000,
        "sector": "Energy",
        "pe": 6,
        "ps": 0.8,
        "operating_margin": 0.25,
        "pct_1w": 0.01,
        "pct_1m": 0.02,
    }
    rich = {
        **cheap,
        "price": 200,
        "pe": 80,
        "ps": 18,
        "free_cashflow_ttm": 1_000_000,
        "fcf_annual": [1_000_000, 2_000_000],
        "net_income_annual": [1_000_000, 3_000_000, 4_000_000],
        "pct_1w": 0.22,
        "pct_1m": 0.45,
        "operating_margin": 0.02,
    }
    scored = score_universe({"CHEAP": cheap, "RICH": rich})
    assert scored["CHEAP"]["undervalued_score"] is not None
    assert scored["RICH"]["overvalued_score"] is not None
    assert top_n(scored, "undervalued_score", 1)[0]["ticker"] == "CHEAP"
    assert top_n(scored, "abs_pct_1w", 1)[0]["ticker"] == "RICH"
