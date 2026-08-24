from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sda.config import OUTPUT_DIR, ensure_dirs
from sda.io_util import latest_file, read_json, write_json
from sda.run_dir import file_in_run, resolve_run_dir
from sda.verdict.chain import run_verdicts


def _index_screen(screen: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for bucket, items in (screen.get("lists") or {}).items():
        for row in items:
            ticker = row.get("ticker")
            if not ticker:
                continue
            if ticker not in rows:
                rows[ticker] = {**row, "buckets": [bucket]}
            elif bucket not in rows[ticker]["buckets"]:
                rows[ticker]["buckets"].append(bucket)
    return rows


def write_verdicts_markdown(path: Path, as_of: str, verdicts: list[dict[str, Any]]) -> Path:
    lines = [
        f"# Watchlist verdicts {as_of}",
        "",
        "Free-form GPT conclusions on screened names plus cleaned company news. Not investment advice.",
        "",
    ]
    for item in verdicts:
        buckets = ", ".join(item.get("buckets") or [])
        lines.append(f"## {item.get('ticker')}")
        lines.append("")
        lines.append(f"- Buckets: {buckets or 'n/a'}")
        lines.append(f"- As of: {item.get('as_of')}")
        lines.append(f"- Kept news items: {item.get('kept_news_count')}")
        lines.append("")
        lines.append(item.get("conclusion") or "_No conclusion._")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_verdicts(
    news_path: str | None = None,
    screen_path: str | None = None,
    run_dir: str | None = None,
) -> dict[str, Any]:
    ensure_dirs()
    folder = resolve_run_dir(run_dir, hint_path=news_path or screen_path)
    news_file = Path(news_path) if news_path else file_in_run(folder, "news_clean.json")
    if news_file is None:
        news_file = latest_file(OUTPUT_DIR, "news_clean_", ".json")
    if news_file is None:
        raise FileNotFoundError("No cleaned news JSON found. Run `python -m sda news` first.")
    news_payload = read_json(news_file)

    screen_file = Path(screen_path) if screen_path else file_in_run(folder, "screen.json")
    if screen_file is None:
        screen_file = latest_file(OUTPUT_DIR, "screen_", ".json")
    screen = read_json(screen_file) if screen_file else news_payload.get("screen") or {}
    if not screen:
        raise FileNotFoundError("No screen JSON found for verdict metrics.")

    verdicts = run_verdicts(news_payload, _index_screen(screen))
    as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    json_path = folder / "verdicts.json"
    payload = {"as_of": as_of, "verdicts": verdicts}
    write_json(json_path, payload)
    md_path = write_verdicts_markdown(folder / "verdicts.md", as_of, verdicts)
    payload["verdicts_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    payload["run_dir"] = str(folder)
    return payload
