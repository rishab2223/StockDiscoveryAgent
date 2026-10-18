from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sda.config import SCREEN_N
from sda.io_util import read_json, write_json
from sda.run_dir import file_in_run, resolve_run_dir
from sda.screen.scorer import score_universe, slim, top_n
from sda.screen.writer import write_screen_csv, write_screen_markdown

ASSUMPTIONS = {
    "undervalued": "growth + cheap sector-relative PE/PS + DCF yield; traps excluded",
    "overvalued": "rich multiples, weak DCF gap, stretched 1m move",
    "dev_1w": "abs pct vs ~5 trading days",
    "dev_1m": "abs pct vs ~21 trading days",
}


def _load_market(market_path: str | None, run_dir: Path) -> dict[str, Any]:
    if market_path:
        return read_json(Path(market_path))
    found = file_in_run(run_dir, "market.json")
    if found is None:
        raise FileNotFoundError(f"No market.json in {run_dir}. Run `python -m sda fetch` first.")
    return read_json(found)


def index_screen(screen: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """ticker -> its screen row plus the buckets it appears in (unique across the four lists)."""
    rows: dict[str, dict[str, Any]] = {}
    for bucket, items in (screen.get("lists") or {}).items():
        for row in items:
            ticker = row.get("ticker")
            if not ticker:
                continue
            entry = rows.setdefault(ticker, {**row, "buckets": []})
            if bucket not in entry["buckets"]:
                entry["buckets"].append(bucket)
    return rows


def run_screen(
    n: int = SCREEN_N,
    market_path: str | None = None,
    run_dir: str | None = None,
) -> dict[str, Any]:
    """Rank the fetched universe and write the four shortlists into the run folder."""
    folder = resolve_run_dir(run_dir, hint_path=market_path)
    market = _load_market(market_path, folder)
    scored = score_universe(market.get("tickers") or {})

    lists = {
        "undervalued": top_n(scored, "undervalued_score", n),
        "overvalued": top_n(scored, "overvalued_score", n),
        "dev_1w": top_n(scored, "abs_pct_1w", n),
        "dev_1m": top_n(scored, "abs_pct_1m", n),
    }
    slim_lists = {key: [slim(row) for row in rows] for key, rows in lists.items()}

    as_of = market.get("as_of") or datetime.now(timezone.utc).isoformat()
    json_path = folder / "screen.json"
    payload = {
        "as_of": as_of,
        "n": n,
        "universe": market.get("universe"),
        "lists": slim_lists,
        "assumptions": ASSUMPTIONS,
    }
    write_json(json_path, payload)
    md_path = write_screen_markdown(folder / "screen.md", as_of, slim_lists)
    csv_path = write_screen_csv(folder / "screen.csv", slim_lists)
    payload["screen_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    payload["csv_path"] = str(csv_path)
    payload["run_dir"] = str(folder)
    return payload
