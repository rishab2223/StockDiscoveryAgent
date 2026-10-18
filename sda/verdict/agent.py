from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sda.io_util import read_json, write_json
from sda.run_dir import file_in_run, resolve_run_dir
from sda.screen.agent import index_screen
from sda.verdict.chain import run_verdicts


def write_verdicts_markdown(path: Path, as_of: str, verdicts: list[dict[str, Any]]) -> Path:
    lines = [
        f"# Watchlist verdicts {as_of}",
        "",
        "Free-form GPT conclusions on screened names plus cleaned company news. Not investment advice.",
        "",
    ]
    for item in verdicts:
        lines += [
            f"## {item.get('ticker')}",
            "",
            f"- Buckets: {', '.join(item.get('buckets') or []) or 'n/a'}",
            f"- As of: {item.get('as_of')}",
            f"- Kept news items: {item.get('kept_news_count')}",
            "",
            item.get("conclusion") or "_No conclusion._",
            "",
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _input(explicit: str | None, run_dir: Path, name: str, hint: str) -> Path:
    found = Path(explicit) if explicit else file_in_run(run_dir, name)
    if found is None:
        raise FileNotFoundError(f"No {name} in {run_dir}. Run `python -m sda {hint}` first.")
    return found


def write_verdicts(
    news_path: str | None = None,
    screen_path: str | None = None,
    run_dir: str | None = None,
) -> dict[str, Any]:
    """Ask the LLM for one conclusion per shortlisted ticker and write verdicts.json / .md."""
    folder = resolve_run_dir(run_dir, hint_path=news_path or screen_path)
    news_payload = read_json(_input(news_path, folder, "news_clean.json", "news"))
    screen = read_json(_input(screen_path, folder, "screen.json", "screen"))

    verdicts = run_verdicts(news_payload, index_screen(screen))
    as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    json_path = folder / "verdicts.json"
    payload = {"as_of": as_of, "verdicts": verdicts}
    write_json(json_path, payload)
    md_path = write_verdicts_markdown(folder / "verdicts.md", as_of, verdicts)
    payload["verdicts_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    payload["run_dir"] = str(folder)
    return payload
