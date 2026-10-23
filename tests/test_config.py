"""Tests for the path/config helpers in :mod:`config`."""

from pathlib import Path

import pytest

import config


def test_container_defaults():
    """Defaults must match the paths baked into the Docker image."""
    assert config.music_dir() == Path("/music/navidrofm")
    assert config.library_root() == Path("/music")
    assert config.csv_playlists_dir() == Path("/app/csv_playlists")
    assert config.cookies_file() == Path("/app/cookies/cookies.txt")
    assert config.blocklist_file() == Path("/app/blocklist.json")
    assert config.lock_file() == Path("/tmp/navidrofm.lock")


@pytest.mark.parametrize(
    ("function", "variable", "value", "expected"),
    [
        (config.music_dir, "NAVIDROFM_MUSIC_DIR", "/tmp/music", Path("/tmp/music")),
        (config.library_root, "NAVIDROFM_LIBRARY_ROOT", "/tmp/lib", Path("/tmp/lib")),
        (config.csv_playlists_dir, "NAVIDROFM_CSV_DIR", "/tmp/csv", Path("/tmp/csv")),
        (
            config.cookies_file,
            "NAVIDROFM_COOKIES_FILE",
            "/tmp/cookies.txt",
            Path("/tmp/cookies.txt"),
        ),
        (
            config.blocklist_file,
            "NAVIDROFM_BLOCKLIST_FILE",
            "/tmp/blocklist.json",
            Path("/tmp/blocklist.json"),
        ),
        (config.lock_file, "NAVIDROFM_LOCK_FILE", "/tmp/lock", Path("/tmp/lock")),
    ],
)
def test_environment_override(function, variable, value, expected, monkeypatch):
    monkeypatch.setenv(variable, value)
    assert function() == expected


def test_empty_environment_variable_falls_back_to_default(monkeypatch):
    """Docker/cron export unset variables as "" -- that must not mean cwd."""
    monkeypatch.setenv("NAVIDROFM_MUSIC_DIR", "")
    assert config.music_dir() == Path("/music/navidrofm")


def test_home_directory_is_expanded(monkeypatch):
    monkeypatch.setenv("NAVIDROFM_MUSIC_DIR", "~/music")
    assert config.music_dir() == Path.home() / "music"


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on", " true "])
def test_env_flag_truthy(raw, monkeypatch):
    monkeypatch.setenv("REMOVE_OLD_TRACKS", raw)
    assert config.env_flag("REMOVE_OLD_TRACKS") is True


@pytest.mark.parametrize("raw", ["0", "false", "no", "off", "garbage"])
def test_env_flag_falsy(raw, monkeypatch):
    monkeypatch.setenv("REMOVE_OLD_TRACKS", raw)
    assert config.env_flag("REMOVE_OLD_TRACKS") is False


def test_env_flag_defaults(monkeypatch):
    assert config.env_flag("REMOVE_OLD_TRACKS") is False
    assert config.env_flag("REMOVE_OLD_TRACKS", default=True) is True
    monkeypatch.setenv("REMOVE_OLD_TRACKS", "")
    assert config.env_flag("REMOVE_OLD_TRACKS", default=True) is True


def test_env_int(monkeypatch):
    assert config.env_int("MIX_TRACKS", 25) == 25
    monkeypatch.setenv("MIX_TRACKS", "")
    assert config.env_int("MIX_TRACKS", 25) == 25
    monkeypatch.setenv("MIX_TRACKS", "100")
    assert config.env_int("MIX_TRACKS", 25) == 100
