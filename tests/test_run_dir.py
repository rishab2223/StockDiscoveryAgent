import pytest

from sda import config
from sda.run_dir import file_in_run, latest_run_dir, latest_run_with, new_run_dir, resolve_run_dir


def test_new_run_dir_lives_under_output():
    path = new_run_dir()
    assert path.parent == config.OUTPUT_DIR and path.is_dir()
    assert path.name.endswith("Z") and "_" in path.name


def test_latest_helpers(tmp_path):
    assert latest_run_dir() is None and latest_run_with("market.json") is None
    older = config.OUTPUT_DIR / "2026-01-01_000000Z"
    newer = config.OUTPUT_DIR / "2026-02-01_000000Z"
    hidden = config.OUTPUT_DIR / ".tmp"
    for p in (older, newer, hidden):
        p.mkdir(parents=True)
    (older / "market.json").write_text("{}")
    (config.OUTPUT_DIR / "stray.txt").write_text("")
    assert latest_run_dir() == newer
    assert latest_run_with("market.json") == older
    assert file_in_run(older, "market.json") == older / "market.json"
    assert file_in_run(newer, "market.json") is None


def test_resolve_run_dir_cases(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_run_dir()

    explicit = resolve_run_dir(tmp_path / "explicit")
    assert explicit.is_dir()

    run = config.OUTPUT_DIR / "2026-03-01_000000Z"
    run.mkdir(parents=True)
    assert resolve_run_dir() == run
    assert resolve_run_dir(hint_path=run / "market.json") == run

    outside = tmp_path / "elsewhere" / "market.json"
    fresh = resolve_run_dir(hint_path=outside)
    assert fresh.parent == config.OUTPUT_DIR and fresh != run
