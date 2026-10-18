import os
import time

from sda import config
from sda.fetch import cache


def test_store_and_load_respect_age():
    assert cache.load("b", "k", 60) is None
    cache.store("b", "k", {"x": 1})
    assert (config.CACHE_DIR / "b" / "k.json").exists()
    assert cache.load("b", "k", 60) == {"x": 1}
    old = time.time() - 3600
    os.utime(config.CACHE_DIR / "b" / "k.json", (old, old))
    assert cache.load("b", "k", 60) is None
    assert cache.load("b", "k", 7200) == {"x": 1}


def test_corrupt_entry_is_ignored():
    cache.store("b", "bad", {"x": 1})
    (config.CACHE_DIR / "b" / "bad.json").write_text("{not json", encoding="utf-8")
    assert cache.load("b", "bad", 60) is None
