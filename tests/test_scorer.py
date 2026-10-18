import math

from sda.screen.scorer import (
    _finite,
    _weighted,
    attach_sector_relatives,
    score_universe,
    slim,
    top_n,
    undervalued_score,
)
from tests.conftest import make_record


def test_finite_rejects_bool_nan_and_none():
    assert _finite(1.5) and _finite(0)
    assert not _finite(True) and not _finite(None) and not _finite(math.nan) and not _finite("3")


def test_sector_relatives_use_positive_medians_only():
    records = {
        "A": {"sector": "Energy", "pe": 10, "ps": 1},
        "B": {"sector": "Energy", "pe": 30, "ps": 3},
        "C": {"sector": "Energy", "pe": -5, "ps": None},
        "D": {"sector": "Utilities", "pe": None, "ps": 2},
    }
    out = attach_sector_relatives(records)
    assert out["A"]["sector_pe_median"] == 20 and out["A"]["pe_vs_sector"] == -0.5
    assert out["B"]["pe_vs_sector"] == 0.5
    assert out["C"]["pe_vs_sector"] == (-5 - 20) / 20
    assert out["D"]["sector_pe_median"] is None and out["D"]["pe_vs_sector"] is None
    assert out["D"]["ps_vs_sector"] == 0.0


def test_weighted_needs_enough_components():
    assert _weighted([(0.2, 0.2)]) is None
    assert _weighted([(0.2, 0.2), (0.3, 0.3)]) == 1.0


def test_undervalued_score_excludes_traps_and_unpriced():
    assert undervalued_score({"value_trap": True, "price": 1, "ni_yoy": 1}) is None
    assert undervalued_score({"price": None, "ni_yoy": 1}) is None
    assert undervalued_score({"price": 1, "ni_yoy": 0.5}) is None  # not enough signal mass


def test_screen_ranks_four_lists_and_normalises_sectors():
    cheap = make_record(sector="Energy")
    rich = make_record(
        sector="Technology",  # Yahoo label -> GICS
        price=200,
        pe=80,
        ps=18,
        free_cashflow_ttm=1_000_000,
        fcf_annual=[1_000_000, 2_000_000],
        net_income_annual=[1_000_000, 3_000_000, 4_000_000],
        pct_1w=0.22,
        pct_1m=0.45,
        operating_margin=0.02,
    )
    # Looks cheap next to RICH, but its earnings halved -> value trap, so it cannot rank.
    peer = make_record(sector="Information Technology", pe=20, ps=4, net_income_annual=[1_000_000, 2_000_000, 2_500_000])
    scored = score_universe({"CHEAP": cheap, "RICH": rich, "PEER": peer})
    assert scored["RICH"]["sector"] == "Information Technology"
    assert scored["RICH"]["sector_pe_median"] == 50  # RICH and PEER share one sector
    assert scored["PEER"]["pe_vs_sector"] == -0.6
    assert scored["CHEAP"]["undervalued_score"] is not None
    assert scored["RICH"]["undervalued_score"] is None  # NI fell 67% -> value trap
    assert scored["PEER"]["undervalued_score"] is None
    assert top_n(scored, "undervalued_score", 1)[0]["ticker"] == "CHEAP"
    assert top_n(scored, "overvalued_score", 1)[0]["ticker"] == "RICH"
    assert top_n(scored, "abs_pct_1w", 1)[0]["ticker"] == "RICH"
    assert [row["ticker"] for row in top_n(scored, "abs_pct_1m", 5)] == ["RICH", "CHEAP", "PEER"]


def test_top_n_skips_missing_values():
    records = {"A": {"ticker": "A", "k": None}, "B": {"ticker": "B", "k": 2.0}, "C": {"ticker": "C"}}
    assert [r["ticker"] for r in top_n(records, "k", 5)] == ["B"]


def test_slim_keeps_export_fields_only():
    row = slim({"ticker": "A", "price": 1.0, "secret": 2})
    assert row["ticker"] == "A" and "secret" not in row and row["dcf_yield"] is None
