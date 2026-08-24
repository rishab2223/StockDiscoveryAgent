from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from sda.screen.scorer import EXPORT_FIELDS, slim


def write_screen_csv(path: Path, lists: dict[str, list[dict[str, Any]]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["bucket", *EXPORT_FIELDS])
        writer.writeheader()
        for bucket, rows in lists.items():
            for row in rows:
                writer.writerow({"bucket": bucket, **slim(row)})
    return path


def _md_table(rows: list[dict[str, Any]]) -> str:
    headers = ["ticker", "price", "pe", "ps", "ni_yoy", "dcf_yield", "pct_1w", "pct_1m", "value_trap"]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        cells = []
        for key in headers:
            value = row.get(key)
            if isinstance(value, float):
                cells.append(f"{value:.3f}" if abs(value) < 100 else f"{value:.1f}")
            else:
                cells.append("" if value is None else str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_screen_markdown(path: Path, as_of: str, lists: dict[str, list[dict[str, Any]]]) -> Path:
    titles = {
        "undervalued": "Undervalued (composite)",
        "overvalued": "Overvalued (composite)",
        "dev_1w": "Largest 1-week absolute deviation",
        "dev_1m": "Largest 1-month absolute deviation",
    }
    chunks = [f"# Screen {as_of}", "", "Local model on yfinance cache. Not investment advice.", ""]
    for key, rows in lists.items():
        chunks.append(f"## {titles.get(key, key)}")
        chunks.append("")
        chunks.append(_md_table(rows) if rows else "_No names qualified._")
        chunks.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(chunks), encoding="utf-8")
    return path
