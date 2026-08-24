from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sma.config import CACHE_DIR, SCREEN_N, ensure_dirs
from sma.io_util import latest_file, read_json, write_json
from sma.run_dir import file_in_run, resolve_run_dir
from sma.screen.scorer import score_universe, slim, top_n
from sma.screen.writer import write_screen_csv, write_screen_markdown


def _load_cache(cache_path: str | None, run_dir: Path | None) -> dict[str, Any]:
    if cache_path:
        path = Path(cache_path)
    elif run_dir and file_in_run(run_dir, "market.json"):
        path = run_dir / "market.json"
    else:
        path = latest_file(CACHE_DIR, "market_", ".json")
        if path is None:
            raise FileNotFoundError("No market cache found. Run `python -m sma fetch` first.")
    return read_json(path)


def run_screen(
    n: int = SCREEN_N,
    cache_path: str | None = None,
    run_dir: str | None = None,
) -> dict[str, Any]:
    """Rank the cached universe and write shortlists into the run folder."""
    ensure_dirs()
    folder = resolve_run_dir(run_dir, hint_path=cache_path)
    cache = _load_cache(cache_path, folder)
    scored = score_universe(cache.get("tickers") or {})

    lists = {
        "undervalued": top_n(scored, "undervalued_score", n),
        "overvalued": top_n(scored, "overvalued_score", n),
        "dev_1w": top_n(scored, "abs_pct_1w", n),
        "dev_1m": top_n(scored, "abs_pct_1m", n),
    }
    slim_lists = {key: [slim(row) for row in rows] for key, rows in lists.items()}

    as_of = cache.get("as_of") or datetime.now(timezone.utc).isoformat()
    json_path = folder / "screen.json"
    payload = {
        "as_of": as_of,
        "n": n,
        "cache_universe": cache.get("universe"),
        "lists": slim_lists,
        "assumptions": {
            "undervalued": "growth + cheap sector-relative PE/PS + DCF yield; traps excluded",
            "overvalued": "rich multiples, weak DCF gap, stretched 1m move",
            "dev_1w": "abs pct vs ~5 trading days",
            "dev_1m": "abs pct vs ~21 trading days",
        },
    }
    write_json(json_path, payload)
    md_path = write_screen_markdown(folder / "screen.md", as_of, slim_lists)
    csv_path = write_screen_csv(folder / "screen.csv", slim_lists)
    payload["screen_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    payload["csv_path"] = str(csv_path)
    payload["run_dir"] = str(folder)
    return payload
