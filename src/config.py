"""Runtime paths and configuration helpers.

All defaults mirror the paths used inside the Docker image, so container
behaviour is unchanged.  Every path can be overridden with an environment
variable, which is what makes it possible to run NavidroFM from a plain git
checkout (and from the test-suite) without creating ``/app`` or ``/music``.

Naming convention: ``NAVIDROFM_<THING>`` for paths that only exist for the
app itself.  Feature settings keep their historical names (``RECOMMENDED``,
``LASTFM_USERNAME``, ...) for backwards compatibility with existing
deployments.
"""

import os
from pathlib import Path

# Container defaults (see Dockerfile / docker-compose-default.yml)
DEFAULT_MUSIC_DIR = "/music/navidrofm"
DEFAULT_LIBRARY_ROOT = "/music"
DEFAULT_CSV_PLAYLISTS_DIR = "/app/csv_playlists"
DEFAULT_COOKIES_FILE = "/app/cookies/cookies.txt"
DEFAULT_BLOCKLIST_FILE = "/app/blocklist.json"
DEFAULT_LOCK_FILE = "/tmp/navidrofm.lock"


def _env_path(variable: str, default: str) -> Path:
    """Return ``variable`` as a Path, falling back to ``default``.

    An empty value is treated as unset.  Docker/cron exports unset variables
    as empty strings, and ``Path("")`` would silently resolve to the current
    working directory.
    """
    value = os.getenv(variable) or default
    return Path(value).expanduser()


def env_flag(variable: str, default: bool = False) -> bool:
    """Read a boolean environment variable (``"true"``/``"1"``/``"yes"``)."""
    value = os.getenv(variable)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(variable: str, default: int) -> int:
    """Read an integer environment variable, falling back to ``default``."""
    value = os.getenv(variable)
    if value is None or value.strip() == "":
        return default
    return int(value)


def music_dir() -> Path:
    """Root folder where downloaded music is stored (``NAVIDROFM_MUSIC_DIR``)."""
    return _env_path("NAVIDROFM_MUSIC_DIR", DEFAULT_MUSIC_DIR)


def library_root() -> Path:
    """Root of the Navidrome music library as mounted in the container.

    Used to build the relative path for selective scans
    (``NAVIDROFM_LIBRARY_ROOT``, defaults to ``/music``).
    """
    return _env_path("NAVIDROFM_LIBRARY_ROOT", DEFAULT_LIBRARY_ROOT)


def csv_playlists_dir() -> Path:
    """Folder scanned for ``*.csv`` playlists (``NAVIDROFM_CSV_DIR``)."""
    return _env_path("NAVIDROFM_CSV_DIR", DEFAULT_CSV_PLAYLISTS_DIR)


def cookies_file() -> Path:
    """yt-dlp cookies file (``NAVIDROFM_COOKIES_FILE``)."""
    return _env_path("NAVIDROFM_COOKIES_FILE", DEFAULT_COOKIES_FILE)


def blocklist_file() -> Path:
    """Artist blocklist JSON file (``NAVIDROFM_BLOCKLIST_FILE``)."""
    return _env_path("NAVIDROFM_BLOCKLIST_FILE", DEFAULT_BLOCKLIST_FILE)


def lock_file() -> Path:
    """Single-instance lock file (``NAVIDROFM_LOCK_FILE``)."""
    return _env_path("NAVIDROFM_LOCK_FILE", DEFAULT_LOCK_FILE)
