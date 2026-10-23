"""Tests for the single-instance lock in :mod:`app`."""

import app


def test_lock_prevents_concurrent_runs(monkeypatch, tmp_path):
    monkeypatch.setenv("NAVIDROFM_LOCK_FILE", str(tmp_path / "navidrofm.lock"))

    first = app.acquire_lock()
    assert first is not None

    try:
        assert app.acquire_lock() is None
    finally:
        app.release_lock(first)

    # Once released the lock can be taken again.
    second = app.acquire_lock()
    assert second is not None
    app.release_lock(second)


def test_release_without_lock_is_safe():
    app.release_lock(None)
