from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sda.config import OUTPUT_DIR, ensure_dirs


def new_run_dir() -> Path:
    """Create output/<UTC timestamp>/ for one pipeline run (Windows-safe name)."""
    ensure_dirs()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%SZ")
    path = OUTPUT_DIR / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def latest_run_dir() -> Path | None:
    if not OUTPUT_DIR.exists():
        return None
    dirs = sorted(
        path
        for path in OUTPUT_DIR.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )
    return dirs[-1] if dirs else None


def resolve_run_dir(
    run_dir: str | Path | None = None,
    hint_path: str | Path | None = None,
    create: bool = False,
) -> Path:
    if run_dir:
        path = Path(run_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    if hint_path:
        parent = Path(hint_path).resolve().parent
        if parent.exists() and parent != OUTPUT_DIR.resolve() and parent.name != "cache":
            return parent
    latest = latest_run_dir()
    if latest:
        return latest
    if create:
        return new_run_dir()
    raise FileNotFoundError("No run folder found. Run `python -m sda fetch` or `python -m sda run` first.")


def file_in_run(run_dir: Path, name: str) -> Path | None:
    path = run_dir / name
    return path if path.exists() else None
