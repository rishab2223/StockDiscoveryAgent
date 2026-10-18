from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sda import config


def new_run_dir() -> Path:
    """Create output/<UTC timestamp>/ for one pipeline run (Windows-safe name)."""
    config.ensure_dirs()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%SZ")
    path = config.OUTPUT_DIR / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def _run_dirs() -> list[Path]:
    if not config.OUTPUT_DIR.exists():
        return []
    return sorted(
        path
        for path in config.OUTPUT_DIR.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def latest_run_dir() -> Path | None:
    dirs = _run_dirs()
    return dirs[-1] if dirs else None


def latest_run_with(name: str) -> Path | None:
    """Newest run folder that already holds `name` (e.g. market.json)."""
    for path in reversed(_run_dirs()):
        if (path / name).exists():
            return path
    return None


def resolve_run_dir(run_dir: str | Path | None = None, hint_path: str | Path | None = None) -> Path:
    """Folder a step writes into: the given run_dir, else the run folder its input
    file lives in, else the newest run. An input from outside output/ gets a fresh
    folder so its results are not mixed into an unrelated run."""
    if run_dir:
        path = Path(run_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    if hint_path:
        parent = Path(hint_path).resolve().parent
        if parent.parent == config.OUTPUT_DIR.resolve():
            return parent
        return new_run_dir()
    latest = latest_run_dir()
    if latest:
        return latest
    raise FileNotFoundError("No run folder found. Run `python -m sda fetch` or `python -m sda run` first.")


def file_in_run(run_dir: Path, name: str) -> Path | None:
    path = run_dir / name
    return path if path.exists() else None
