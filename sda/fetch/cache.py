"""Small on-disk JSON cache so repeat runs skip slow per-ticker Yahoo calls.

Entries live at data/cache/<bucket>/<key>.json and expire by file age.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from sda import config


def _path(bucket: str, key: str) -> Path:
    return config.CACHE_DIR / bucket / f"{key}.json"


def load(bucket: str, key: str, max_age_s: float) -> Any | None:
    path = _path(bucket, key)
    try:
        if time.time() - path.stat().st_mtime > max_age_s:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def store(bucket: str, key: str, payload: Any) -> None:
    path = _path(bucket, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, default=str), encoding="utf-8")
