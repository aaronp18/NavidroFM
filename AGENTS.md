# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.
**Keep this file up to date** when you change architecture, commands or
conventions. It is the single source of truth; `CLAUDE.md` links here.

## What this project is

NavidroFM is a Python 3.12 job/container that builds "Spotify-like" playlists
in [Navidrome](https://www.navidrome.org/):

1. Collect tracks from LastFM recommendations, ListenBrainz weekly playlists,
   or user-supplied CSV exports (`csv_playlists/*.csv`).
2. Skip anything already in the Navidrome library (Subsonic `search3`).
3. Otherwise search YouTube Music (`ytmusicapi`) and download audio with
   `yt-dlp` (`--audio-format mp3`).
4. Write ID3 tags/cover art (`mutagen`) and drop files into
   `<music>/navidrofm/<source>/`.
5. Create/update the Navidrome playlist through the Subsonic API.

It normally runs as a cron-driven Docker container: `entrypoint.sh` generates
`/app/cron-env.sh` and a crontab entry, then runs `src/app.py all`. It can also
be run as a one-shot CLI.

## Quick start (local, no Docker)

```bash
make install-dev            # creates ./venv, installs runtime + dev deps
cp .env.example .env        # fill in credentials; .env is git-ignored
make check                  # ruff + pytest (no network required)

make run TYPE=csv           # runs src/app.py csv, sourcing .env
make run TYPE=all           # recommended, mix, library, exploration, jams, csv
```

`TYPE` is one of `recommended | mix | library | exploration | jams | csv | all`.

For local runs the app needs path overrides, because the defaults point at
container locations (`/app/...`, `/music/...`). Uncomment the `NAVIDROFM_*`
block at the bottom of `.env` (e.g. `NAVIDROFM_CSV_DIR=./csv_playlists`,
`NAVIDROFM_MUSIC_DIR=./.local/music`). Nothing is written until a playlist is
actually synced.

## Commands

| Command                   | Purpose                                                |
| ------------------------- | ------------------------------------------------------ |
| `make help`               | List all targets                                       |
| `make install-dev`        | Create `./venv` and install `requirements-dev.txt`      |
| `make lint`               | `ruff check .`                                         |
| `make format`             | `ruff check --fix` + `ruff format`                     |
| `make test`               | `pytest` (unit tests, no network)                      |
| `make test-cov`           | `pytest --cov=src --cov-report=term-missing`            |
| `make check`              | **Gate**: lint + test (same as CI)                     |
| `make run TYPE=<type>`    | Run locally with `.env` sourced                        |
| `make docker-build`       | `docker build -t aaronp18/navidrofm:dev .`             |
| `make docker-build-multi` | Build amd64 + arm64 images (no push)                   |
| `make docker-up`/`down`   | `docker compose up -d --build` / `down`                 |
| `make clean`              | Remove caches/coverage artifacts                       |

CI (`.github/workflows/ci.yml`) runs `ruff check .`, `pytest --cov` and a
Docker build on every push/PR.

## Repository map

```
src/app.py                 CLI entrypoint; argparse, single-instance flock lock
src/navidroFM.py           Composition root: wires Navidrome + YTDLP + syncers
src/config.py              Paths/flags from env with container defaults ← start here
src/blocklist.py           Optional artist blocklist loader (JSON)
src/navidrome.py           Subsonic API client: search, scan, playlist CRUD
src/ytdlp.py               YouTube Music search + yt-dlp download + tagging
src/Util.py                Pure helpers: filename sanitising, matching, metadata
src/csvPlaylistSyncer.py   CSV parsing + CSV playlist sync
src/lastFMListenBrainz.py  LastFM/ListenBrainz playlist sync
src/legacy.py              Pre-refactor monolith, NOT imported. Do not extend.
entrypoint.sh              Docker entrypoint: writes cron env + crontab, starts cron
Dockerfile                 python:3.12-slim + ffmpeg + deno + requirements.txt
tests/                     pytest suite (pure unit tests, no network)
test.py                    Manual yt-dlp scratch script; not collected by pytest
```

## Data flow (one sync)

```
app.py <type>
  └─ NavidroFM()                        (navidroFM.py)
       ├─ Navidrome()                   ping /rest/ping, builds Subsonic params
       ├─ YTDLP()                       ytmusicapi client, cookie path
       ├─ CSVPlaylistSyncer(...)        reads CSV dir at construction time
       └─ ListenBrainzLastFM(...)       builds per-playlist config from env

  CSVPlaylistSyncer.syncPlaylists()
       └─ per playlist: get/create playlist → for each track:
            Navidrome.search_navidrome_track()
            YTDLP.search_ytmusic_track() → YTDLP.download_track_ytmusic()
            Navidrome.scan_and_get_songs_from_directory()
            Navidrome.update_playlist()

  ListenBrainzLastFM.sync_playlist(type) → same download/tag/scan pattern
```

## Configuration

All settings come from environment variables (`.env` locally, `environment:` in
docker-compose for production):

| Variable                                                    | Meaning                                                     |
| ----------------------------------------------------------- | ----------------------------------------------------------- |
| `NAVIDROME_URL`, `NAVIDROME_USERNAME`, `NAVIDROME_PASSWORD`  | Required for any sync                                       |
| `NAVIDROME_LIBRARY_ID`                                       | Library id for selective scans (default `1`)                |
| `LASTFM_USERNAME`                                            | Required for LastFM playlists                               |
| `RECOMMENDED`, `MIX`, `LIBRARY` + `*_TRACKS`, `*_SCHEDULE`   | LastFM toggles (default off)                                |
| `LZ_USERNAME`                                                | Required for ListenBrainz playlists                         |
| `EXPLORATION`, `JAMS` + `*_TRACKS`, `*_SCHEDULE`             | ListenBrainz toggles (track count capped at 50)             |
| `CSV_ENABLED`                                                | Enables CSV syncs (the CSV syncer also loads files eagerly) |
| `SYNC_SCHEDULE`                                              | Cron expression for the container job                       |
| `RUN_ON_STARTUP`                                             | Run `app.py all` before starting cron                       |
| `REMOVE_OLD_TRACKS`                                          | `true` deletes downloaded mp3s before re-downloading        |
| `TZ`                                                         | Timezone for logs/schedules                                 |
| `NAVIDROFM_MUSIC_DIR`                                        | Downloads root (default `/music/navidrofm`)                 |
| `NAVIDROFM_LIBRARY_ROOT`                                     | Navidrome library root for scan targets (default `/music`)  |
| `NAVIDROFM_CSV_DIR`                                          | CSV playlist folder (default `/app/csv_playlists`)          |
| `NAVIDROFM_COOKIES_FILE`                                     | yt-dlp cookies (default `/app/cookies/cookies.txt`)         |
| `NAVIDROFM_BLOCKLIST_FILE`                                   | Artist blocklist JSON (default `/app/blocklist.json`)       |
| `NAVIDROFM_LOCK_FILE`                                        | Single-instance lock (default `/tmp/navidrofm.lock`)        |

Boolean parsing: use `config.env_flag()` (`1/true/yes/on`, case-insensitive).
Integer parsing: `config.env_int()`.

**Container gotcha:** cron jobs do not inherit the container environment.
`entrypoint.sh` writes every variable it needs into `/app/cron-env.sh`; a new
environment variable must be added there or scheduled runs will not see it.

## Filesystem layout (container)

```
/music                      ← host music library (Navidrome must see the same path)
/music/navidrofm/<source>/  ← downloads: recommended, mix, exploration, jams,
                              csv_playlists/<playlist name>/
/app/csv_playlists/*.csv    ← playlist inputs
/app/cookies/cookies.txt    ← yt-dlp cookies
/app/blocklist.json         ← optional artist blocklist
```

CSV format: `IGNORED, Song Title, Artist Name`. Only columns 2 and 3 are used;
a header row (`ID`, `Title`, `Artist`, `#`, `Song`) is skipped. Download/search
failures are appended to `<playlist dir>/failed_tracks.csv` for manual follow-up.
CSV parsing uses `pyparsing` because artist fields can contain commas.

## Conventions

- **Flat imports**: modules live directly in `src/` and import each other by
  bare name (`from navidrome import Navidrome`). Run with `src/` on
  `sys.path` (`python src/app.py`, `PYTHONPATH=src`, or pytest's
  `pythonpath = ["src"]` from `pyproject.toml`). Do not add relative imports.
- **No hardcoded container paths** in new code: add a getter to
  `src/config.py` and use it, so tests/local runs can override it.
- **Logging**: module-level `logger = logging.getLogger(__name__)` and
  `logger.info(...)`; logs go to stdout (`PYTHONUNBUFFERED=1`).
- **Style**: keep the existing camelCase method names in the syncer classes;
  new helpers/tests use snake_case. `ruff` enforces import sorting and
  pyflakes. Line length 100; run `make format` (ruff format) before finishing.
- **Dependencies**: add runtime packages to `requirements.txt` only (the
  Dockerfile installs from it). Dev-only packages go in `requirements-dev.txt`.
- **Never commit**: `.env`, `cookies.txt`, `docker-compose.yml` (holds real
  credentials), `csv_playlists/` contents, downloaded audio.
- **Secrets**: read-only access via environment variables; never log
  credentials. `NAVIDROME_PASSWORD` must not appear in tests or docs.

## Testing

- Tests live in `tests/`; pytest is configured in `pyproject.toml`
  (`pythonpath = ["src"]`, `testpaths = ["tests"]`).
- Tests must be hermetic: **no network, no `/app` or `/music` access**. Use
  `tmp_path` and `monkeypatch.setenv(...)`; `tests/conftest.py` clears all
  known env vars automatically.
- Prefer testing pure functions (`Util`, `parse_csv_playlist`, `config`,
  `load_blocked_artists`) over classes that talk to the network.
- For HTTP code, mock `requests.get` with `monkeypatch`/`unittest.mock`.
- Run a subset with
  `venv/bin/python -m pytest tests/test_csv_parsing.py -k artist`.

## How to add a new playlist source

1. Add the toggle/track-count env vars to the relevant syncer config (or
   `src/config.py`), export them in `entrypoint.sh` (cron env) and document
   them in `README.md`, `.env.example` and the table above.
2. Implement a `sync_playlist()`-style method that produces
   `{"artist": ..., "title": ...}` candidates; reuse the download/tag/scan
   pattern from `lastFMListenBrainz.py`.
3. Wire it into `NavidroFM.runLastFMListenBrainz()` or `app.py`, including the
   new `--type` value in `argparse`.
4. Add unit tests for the parsing/filtering logic (mock HTTP).
5. Update the playlist table in the README.

## Pitfalls / gotchas

- `yt-dlp` is invoked as a subprocess and needs `ffmpeg` on `PATH`. In Docker
  it is downloaded at build time; locally install it (`apt install ffmpeg`).
- YouTube downloads often fail without cookies. The file is optional at
  runtime (a warning is logged) but strongly recommended.
- Selective scan uses a path relative to `NAVIDROFM_LIBRARY_ROOT`
  (`"<libraryId>:<relative path>"`); if the download dir is outside it the code
  falls back to a full scan.
- `app.py` takes an exclusive `flock`; a second concurrent invocation logs an
  error and exits **0** (so cron does not report failures).
- `src/legacy.py` is dead code kept for reference — excluded from ruff; never
  import it from the new modules.
- `test.py` at the repo root is a manual yt-dlp experiment; it is not part of
  the test suite (pytest only collects `test_*.py` / `*_test.py`).
- `docker-compose.yml` is intentionally git-ignored because it holds real
  credentials; `docker-compose-default.yml` is the tracked template and uses
  `${VAR:-default}` interpolation from `.env`.
- `entrypoint.sh` exits non-zero when no playlist is enabled — expected
  behaviour, not a crash.

## Definition of done

- `make check` passes (ruff + pytest).
- New logic has unit tests that need neither network nor a Navidrome server.
- Docs updated (`README.md`, this file, `.env.example`) when behaviour or
  configuration changes.
- No secrets, cookies or downloaded media added to git.
