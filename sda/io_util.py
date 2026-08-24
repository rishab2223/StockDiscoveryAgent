from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_file(directory: Path, prefix: str, suffix: str) -> Path | None:
    if not directory.exists():
        return None
    matches = sorted(directory.glob(f"{prefix}*{suffix}"))
    return matches[-1] if matches else None
