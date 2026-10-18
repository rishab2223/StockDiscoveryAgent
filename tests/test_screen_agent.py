import csv
import json

import pytest

from sda import config
from sda.screen.agent import run_screen
from tests.conftest import make_record, write_run


def _market():
    return {
        "as_of": "2026-10-01T00:00:00+00:00",
        "universe": "custom",
        "tickers": {
            "CHEAP": make_record(),
            "RICH": make_record(sector="Technology", pe=80, ps=18, pct_1w=0.22, pct_1m=0.45, net_income_annual=[1, 3, 4]),
            "PEER": make_record(sector="Technology", pe=20, ps=4, net_income_annual=[1, 2, 3]),  # trap
            "NOPRICE": make_record(price=None),
        },
    }


def test_run_screen_writes_json_md_csv_into_latest_run():
    run_dir = write_run(config.OUTPUT_DIR / "2026-10-01_000000Z", market=_market())
    payload = run_screen(n=2)
    assert payload["run_dir"] == str(run_dir)
    on_disk = json.loads((run_dir / "screen.json").read_text(encoding="utf-8"))
    assert on_disk["as_of"] == "2026-10-01T00:00:00+00:00" and on_disk["n"] == 2 and on_disk["universe"] == "custom"
    assert [r["ticker"] for r in on_disk["lists"]["undervalued"]][0] == "CHEAP"
    assert [r["ticker"] for r in on_disk["lists"]["dev_1w"]] == ["RICH", "CHEAP"]
    assert all(len(rows) <= 2 for rows in on_disk["lists"].values())
    assert "margin_stdev" in on_disk["lists"]["undervalued"][0] and "ebit_annual" not in on_disk["lists"]["undervalued"][0]

    md = (run_dir / "screen.md").read_text(encoding="utf-8")
    assert "## Undervalued (composite)" in md and "| CHEAP |" in md and "_No names qualified._" not in md
    with (run_dir / "screen.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["bucket"] == "undervalued" and rows[0]["ticker"] == "CHEAP"
    assert {r["bucket"] for r in rows} == {"undervalued", "overvalued", "dev_1w", "dev_1m"}


def test_run_screen_with_explicit_market_outside_output(tmp_path):
    elsewhere = write_run(tmp_path / "elsewhere", market={"as_of": None, "tickers": {}})
    payload = run_screen(n=3, market_path=str(elsewhere / "market.json"))
    assert payload["lists"] == {"undervalued": [], "overvalued": [], "dev_1w": [], "dev_1m": []}
    assert payload["as_of"]  # falls back to now
    md = (tmp_path / "output").glob("*/screen.md")
    assert "_No names qualified._" in next(md).read_text(encoding="utf-8")


def test_run_screen_requires_market():
    write_run(config.OUTPUT_DIR / "2026-10-01_000000Z")
    with pytest.raises(FileNotFoundError):
        run_screen()

