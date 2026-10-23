# NavidroFM
Generate automatic Spotify-like playlists for your Navidrome instance, as well as automatically creating playlists from csv files.

## Aaron's Fork Information
- This is a fork of [NavidroFM](https://github.com/4rft5/NavidroFM), which is great for LastFM and ListenBrainz recommended playlists but I wanted to automatically sync playlists such as Top 40 etc.
- Therefore I refactored the codebase to making adding other sources of playlists easier.
- CSV files need to have the following format. All other fields are ignored (as websites export in slightly different formats). The script ignores the header row if it contains words such as ID, Title, Artist, etc
```
IGNORED, Song Title, Artist Name
```
- There are many websites that will export your playlists in `.csv` format. One that I have used is: [Chosic](https://www.chosic.com/spotify-playlist-exporter/#).
- In the future, I would like to add support for automatically doing this from the script (so it can be run on a schedule). Playlists such as the Top40 would benifit from this.
- I've also added support for ARM64 architecture, so you can run this on a Raspberry Pi etc.
- Songs that cannot be downloaded from YT music or found in Navidrome are logged in `failed_tracks.csv` in the playlist directory for manual review and downloading.

- I have recently started using AI agents to help with some development. I still like to do the thinking part, just the boilerplate and repetative programming can be done by AI.


### TODO
- [X] Refactor codebase
- [X] Add CSV playlist support
- [ ] Add support for automatically syncing CSV playlists with online source
- [ ] Add optional [Beets](https://beets.readthedocs.io/en/stable/index.html) auto library management so that on a sync, new songs are added to the library and metadata is cleaned up.
- [ ] Attempt to reduce image size
- [X] Add ARM64 support.
- [ ] Change update frequency of different playlists. For example, the Top 40 would need to be updated more frequently than the LastFM recommended playlist.
- [X] Create log of failed downloads and searches to attempt to download manually

# About
This tool uses public scrobble history to get information about your music taste and recommendations, downloads those songs via [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ytmusicapi](https://github.com/sigma67/ytmusicapi), then imports them as Navidrome playlists for you to listen to.

It also can load `.csv` files from the `csv_playlists` directory and create playlists based on the song title and artist name in those files. Useful for exporting playlists from other services or creating your own custom playlists.

I have used [Chosic](https://www.chosic.com/spotify-playlist-exporter/#) to export playlists from Spotify in the correct format.

## Playlists

| Provider     | Playlist             | Function                                              |
| ------------ | -------------------- | ----------------------------------------------------- |
| LastFM       | Discover Recommended | Recommendations of songs you may like.                |
| LastFM       | Recommended Mix      | Mix of tracks to discover and tracks you know.        |
| LastFM       | Library Mix          | Mix of songs from your existing library.              |
| ListenBrainz | Weekly Exploration   | Discover new tracks based on your history.            |
| ListenBrainz | Weekly Jams          | Mix of songs, both new and from your library.         |
| CSV          | Custom Playlists     | Create playlists from csv files in `./csv_playlists/` |

Note: The LastFM Library playlist will never download any tracks, instead it simply queries the songs and searches Navidrome for them to add to the playlist.

<details>
<summary>LastFM Endpoint Info</summary>
Currently, the tool uses the following LastFM json endpoints (courtesy of u/stdeem):

Discover Recommended: https://www.last.fm/player/station/user/username/recommended

Recommended Mix: https://www.last.fm/player/station/user/username/mix

Library Mix: https://www.last.fm/player/station/user/username/library
</details>

## How it Works
This tool runs on a cron schedule using `TZ` that gets songs from the endpoints based on the usernames you provide in `docker-compose`.

After querying enough songs (plus backups in case a download or search fails) to fulfill the playlist criteria, the tool begins querying the YouTube Music API to find and download the tracks and apply correct metadata. Already existing tracks in Navidrome are skipped. Once the download is complete, the tool searches Navidrome for the tracks and adds them to the corresponding playlist.

For CSV playlist downloading, the program looks for any csv files in the `csv_playlists` directory and creates playlists based on the filename (without the .csv). It then parses the csv file for song title and artist name, searches Navidrome for the track, and adds it to the playlist. If it cannot be found it uses YT Music to download it. The tool ignores the header row if it contains words such as ID, Title, Artist, etc. Any failed downloads or searches are logged in `failed_tracks.csv` in the playlist directory for manual review and downloading.

When the cron schedule re-runs, it deletes previously downloaded tracks (and never your local tracks) and begins the process again. Set `REMOVE_OLD_TRACKS=false` to keep downloaded files and skip re-downloading existing tracks.

# Installation
1. Copy the compose template and create your environment file:

   ```bash
   cp docker-compose-default.yml docker-compose.yml
   cp .env.example .env
   ```

   `docker-compose-default.yml` interpolates every setting from `.env`, so you
   normally do not need to edit the YAML at all. `docker-compose.yml` and `.env`
   are git-ignored because they hold your credentials.
2. Configure your environment variables (in `.env`, using `KEY=value` syntax):

   Cron defaults to 4:00am on Mondays.
  ```
      TZ: Your/Timezone
      NAVIDROME_URL: http://navidrome:4533
      NAVIDROME_USERNAME: username
      NAVIDROME_PASSWORD: password
      SYNC_SCHEDULE: "0 4 * * 1"
  ```
1. Configure playlist variables

   Playlists all default to false but can be enabled with `"true"` (See below).

      3.1 LastFM

      The default track count for both Recommended playlists defaults to 25, Library is 50.
      ```
         LASTFM_USERNAME: username
         RECOMMENDED: "true"
         RECOMMENDED_TRACKS: "25"
         MIX: "true"
         MIX_TRACKS: "25"
         LIBRARY: "true"
         LIBRARY_TRACKS: "50"
      ```

      3.2 ListenBrainz

      The default track count for both playlists defaults to 25 with a max of 50.
      ```
         LZ_USERNAME: username
         EXPLORATION: "true"
         EXPLORATION_TRACKS: "25"
         JAMS: "true"
         JAMS_TRACKS: "25"
      ```

2. Set volumes (via `.env` when using the template, or directly in compose)

   Point `MUSIC_LIBRARY_PATH` at the same library Navidrome uses. The tool makes
   its own `navidrofm` folder inside it for downloaded songs.

   ```bash
   MUSIC_LIBRARY_PATH=/your/music/library
   COOKIES_FILE_PATH=./cookies.txt       # Optional
   BLOCKLIST_FILE_PATH=./blocklist.json  # Optional
   CSV_PLAYLISTS_PATH=./csv_playlists    # Optional
   ```

   4.1 Cookies

      A cookie file [(is highly recommended)](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies). This lets yt-dlp download more reliably.

   4.2 Blocklist

      If you don't want to download songs from a specific artist, you can add a blocklist.json file to skip them when downloading. See the `blocklist.json` file in files for an example.

   4.3 Deleting downloaded tracks

      By default, the tool deletes all downloaded tracks on each run. If you want to keep the downloaded tracks, you can set `REMOVE_OLD_TRACKS: "false"`. This will keep all downloaded tracks in the `navidrofm` folder and skip the download if the track already exists. This is useful if you want to manage your library with something like Beets and don't want to redownload songs every time.

3. Deploy and test

   Run `docker compose up -d`.

   If you want the sync to run on start, you can set `RUN_ON_STARTUP: "true"`. Otherwise, the sync will run once it gets the first run from cron.

   The tool will run and download tracks as outlined above.

## Development

All day-to-day commands are in the `Makefile` (`make help` lists them).
Contributors and AI agents should read [`AGENTS.md`](AGENTS.md) first — it
documents the architecture, data flow, conventions, testing rules and gotchas.

### Prerequisites

- Python 3.12
- `ffmpeg` on `PATH` if you download tracks locally (`yt-dlp` needs it)
- Docker (optional, only for building/running the image)

### Setup

```bash
make install-dev        # create ./venv, install runtime + dev dependencies
cp .env.example .env    # credentials (and local path overrides, see below)
make check              # ruff + pytest, no network required
```

### Running locally

```bash
make run TYPE=csv       # or: recommended | mix | library | exploration | jams | all
```

`make run` sources `.env`. Because the defaults are container paths
(`/app/...`, `/music/...`), uncomment the local overrides in `.env`:

```bash
NAVIDROFM_MUSIC_DIR=./.local/music
NAVIDROFM_LIBRARY_ROOT=./.local/music
NAVIDROFM_CSV_DIR=./csv_playlists
NAVIDROFM_COOKIES_FILE=./cookies.txt
NAVIDROFM_BLOCKLIST_FILE=./blocklist.json
```

The code is a flat set of modules in `src/`, so run it as
`venv/bin/python -u src/app.py <type>` or set `PYTHONPATH=src`.

VS Code is pre-configured (`.vscode/`) with the interpreter, ruff formatting,
pytest integration, debug launch configurations and tasks.

### Tests and linting

| Command         | Description                                     |
| --------------- | ----------------------------------------------- |
| `make lint`     | `ruff check .`                                  |
| `make format`   | Auto-fix and reformat (`ruff`)                  |
| `make test`     | Run the unit tests (hermetic, no network)       |
| `make test-cov` | Tests with coverage for `src/`                  |
| `make check`    | Lint + tests — the gate used by CI              |

Tests live in `tests/`. They never touch the network or `/app`/`/music`; paths
are injected with `NAVIDROFM_*` environment variables and `tmp_path`.

## Contributions
If you want to add something or clean up code, feel free to open a PR on this repo.

At the time of writing, 4rft5 (the original author) is requesting assistance for the following:

   * Making the image smaller (I'm not good at Docker optimization)

   * A reliable, faster way to scan the library after a download is done. I might skip scanning entirely and just use smart playlists. Let me know how you'd like to see this implemented.

### Building Docker Container
- Building docker containers are quite straight forward.
- To build multiplatform images (amd64 and arm64), you can use the following command:

```
docker buildx build --platform linux/amd64,linux/arm64 -t yourusername/navidrofm --push .
```

## Issues
If you encounter an issue, you can open an issue here. Please provide logs from everything to help me better help you.
