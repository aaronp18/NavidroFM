"""Shared pytest fixtures.

Tests must be hermetic: never depend on the environment of the machine or
container running them.  ``clean_env`` removes every variable NavidroFM reads
so individual tests have to opt in to whatever they need.
"""

import pytest

# Every environment variable read through src/config.py or directly via os.getenv
ENV_VARS = [
    # NavidroFM-managed paths
    "NAVIDROFM_MUSIC_DIR",
    "NAVIDROFM_LIBRARY_ROOT",
    "NAVIDROFM_CSV_DIR",
    "NAVIDROFM_COOKIES_FILE",
    "NAVIDROFM_BLOCKLIST_FILE",
    "NAVIDROFM_LOCK_FILE",
    # Credentials / accounts
    "NAVIDROME_URL",
    "NAVIDROME_USERNAME",
    "NAVIDROME_PASSWORD",
    "NAVIDROME_LIBRARY_ID",
    "LASTFM_USERNAME",
    "LZ_USERNAME",
    # Feature toggles
    "RECOMMENDED",
    "RECOMMENDED_TRACKS",
    "RECOMMENDED_SCHEDULE",
    "MIX",
    "MIX_TRACKS",
    "MIX_SCHEDULE",
    "LIBRARY",
    "LIBRARY_TRACKS",
    "LIBRARY_SCHEDULE",
    "EXPLORATION",
    "EXPLORATION_TRACKS",
    "EXPLORATION_SCHEDULE",
    "JAMS",
    "JAMS_TRACKS",
    "JAMS_SCHEDULE",
    "CSV_ENABLED",
    "CSV_SCHEDULE",
    "SYNC_SCHEDULE",
    "REMOVE_OLD_TRACKS",
    "RUN_ON_STARTUP",
    "TZ",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove NavidroFM environment variables for the duration of a test."""
    for variable in ENV_VARS:
        monkeypatch.delenv(variable, raising=False)
    return monkeypatch
