"""Tests for the optional artist blocklist."""

import json

from blocklist import load_blocked_artists


def test_missing_file_returns_empty_set(monkeypatch, tmp_path):
    monkeypatch.setenv("NAVIDROFM_BLOCKLIST_FILE", str(tmp_path / "missing.json"))
    assert load_blocked_artists() == set()


def test_loads_and_normalises_artist_names(monkeypatch, tmp_path):
    path = tmp_path / "blocklist.json"
    path.write_text(json.dumps({"artists": ["Artist 1", "  ARTIST Two  "]}))
    monkeypatch.setenv("NAVIDROFM_BLOCKLIST_FILE", str(path))

    assert load_blocked_artists() == {"artist 1", "artist two"}


def test_missing_artists_key_returns_empty_set(monkeypatch, tmp_path):
    path = tmp_path / "blocklist.json"
    path.write_text(json.dumps({"unexpected": []}))
    monkeypatch.setenv("NAVIDROFM_BLOCKLIST_FILE", str(path))

    assert load_blocked_artists() == set()


def test_invalid_json_is_not_fatal(monkeypatch, tmp_path):
    path = tmp_path / "blocklist.json"
    path.write_text("{not json")
    monkeypatch.setenv("NAVIDROFM_BLOCKLIST_FILE", str(path))

    assert load_blocked_artists() == set()


def test_explicit_path_argument(tmp_path):
    path = tmp_path / "custom.json"
    path.write_text(json.dumps({"artists": ["Blocked"]}))

    assert load_blocked_artists(path) == {"blocked"}
