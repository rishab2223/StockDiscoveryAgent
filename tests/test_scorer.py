from sda.screen.scorer import score_universe, top_n
from tests.conftest import make_record


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
