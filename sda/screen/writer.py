from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from sda.screen.scorer import EXPORT_FIELDS

TITLES = {
    "undervalued": "Undervalued (composite)",
    "overvalued": "Overvalued (composite)",
    "dev_1w": "Largest 1-week absolute deviation",
    "dev_1m": "Largest 1-month absolute deviation",
}
MD_COLUMNS = ["ticker", "price", "pe", "ps", "ni_yoy", "dcf_yield", "pct_1w", "pct_1m", "value_trap"]


def write_screen_csv(path: Path, lists: dict[str, list[dict[str, Any]]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["bucket", *EXPORT_FIELDS], extrasaction="ignore")
        writer.writeheader()
        for bucket, rows in lists.items():
            for row in rows:
                writer.writerow({"bucket": bucket, **row})
    return path


def _cell(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}" if abs(value) < 100 else f"{value:.1f}"
    return "" if value is None else str(value)


def _md_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| " + " | ".join(MD_COLUMNS) + " |",
        "| " + " | ".join("---" for _ in MD_COLUMNS) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(row.get(key)) for key in MD_COLUMNS) + " |")
    return "\n".join(lines)


def write_screen_markdown(path: Path, as_of: str, lists: dict[str, list[dict[str, Any]]]) -> Path:
    chunks = [f"# Screen {as_of}", "", "Local model on Yahoo data. Not investment advice.", ""]
    for key, rows in lists.items():
        chunks += [f"## {TITLES.get(key, key)}", "", _md_table(rows) if rows else "_No names qualified._", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(chunks), encoding="utf-8")
    return path
