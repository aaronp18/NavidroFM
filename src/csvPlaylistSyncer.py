#!/usr/bin/env python3
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import pyparsing

from config import csv_playlists_dir, env_flag
from navidrome import Navidrome
from ytdlp import YTDLP

logger = logging.getLogger(__name__)

# First cell of a header row, as exported by the various playlist exporters
# (see https://www.chosic.com/spotify-playlist-exporter/ for an example).
CSV_HEADER_MARKERS = {"id", "title", "artist", "#", "song"}


def parse_csv_playlist(csv_path: Path) -> List[Dict[str, object]]:
    """Parse a CSV playlist export into ``[{"artists": [...], "title": ...}]``.

    Exports differ slightly between services, so parsing is forgiving:

    * only columns 2 (title) and 3 (artists) are used, everything else is ignored
    * a header row (``ID``, ``Title``, ``Artist``, ``#``, ``Song``) is skipped
    * blank or unparseable lines are skipped instead of aborting the whole file

    Expected format::

        IGNORED, Song Title, Artist Name
    """
    tracks: List[Dict[str, object]] = []

    with open(csv_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Parsing is done with pyparsing because artist fields may themselves
    # contain commas; a naive ``split(",")`` would break them.
    csv_line = pyparsing.common.comma_separated_list.copy().add_parse_action(
        pyparsing.token_map(lambda s: s.strip('"'))
    )

    for line in lines:
        if not line.strip():
            continue

        try:
            parts = csv_line.parse_string(line.strip()).as_list()
        except pyparsing.ParseBaseException:
            logger.warning("Skipping unparseable line in %s: %r", csv_path.name, line)
            continue

        if len(parts) < 3:
            continue

        # Header row, e.g. "ID,Title,Artist"
        if str(parts[0]).lower() in CSV_HEADER_MARKERS:
            continue

        title = str(parts[1]).replace('"', "").replace("'", "").strip()
        artists = [
            artist.strip()
            for artist in str(parts[2])
            .replace('"', "")
            .replace("'", "")
            .strip()
            .split(",")
        ]
        tracks.append({"artists": artists, "title": title})

    return tracks


class CSVPlaylistSyncer:

    def __init__(self, navidrome: Navidrome, ytdlp: YTDLP):
        self.navidrome = navidrome
        self.ytdlp = ytdlp
        self.csv_playlists: Dict[str, List[Dict[str, str]]] = {}
        self.loadCSVFiles()

        self.removeOldTracks = env_flag("REMOVE_OLD_TRACKS")

    def loadCSVFiles(self):
        """Load every ``*.csv`` file from the configured playlists directory."""

        self.csv_playlists = {}
        csv_dir = csv_playlists_dir()
        logger.info("Loading CSV playlists from: %s", csv_dir)
        if csv_dir.exists() and csv_dir.is_dir():
            # Sorted so runs (and tests) are deterministic.
            for csv_file in sorted(csv_dir.glob("*.csv")):
                playlist_name = csv_file.stem
                try:
                    tracks = parse_csv_playlist(csv_file)
                    for track in tracks:
                        logger.info(
                            f"  Loaded track: {track['title']} by {', '.join(track['artists'])}"
                        )
                    self.csv_playlists[playlist_name] = tracks
                    logger.info(
                        f"Loaded CSV playlist '{playlist_name}' with {len(tracks)} tracks"
                    )
                except Exception as e:
                    logger.warning(f"Failed to load CSV playlist '{playlist_name}': {e}")
        logger.info(f"Total CSV playlists loaded: {len(self.csv_playlists)}")

    def syncPlaylist(self, playlist_name: str):
        # Sync a specific playlist to Navidrome
        if playlist_name not in self.csv_playlists:
            logger.warning(f"Playlist '{playlist_name}' not found in CSV playlists")
            return

        tracks = self.csv_playlists[playlist_name]
        logger.info(f"Syncing playlist '{playlist_name}' with {len(tracks)} tracks")

        # Setup with Navidrome
        playlist_id = self.navidrome.get_navidrome_playlist_id(playlist_name)
        if not playlist_id:
            logger.info("Failed to get/create playlist")
            return

        # Create directory for music
        playlist_dir = Path(self.navidrome.music_dir, "csv_playlists", playlist_name)

        if playlist_dir.exists():
            # Clear old songs in the playlist directory if enabled
            if self.removeOldTracks:
                logger.info(f"\nClearing old songs in {playlist_dir}")
                file_count = 0
                for file in playlist_dir.glob("*.mp3"):
                    if file.is_file():
                        try:
                            file.unlink()
                            file_count += 1
                        except Exception as e:
                            logger.info(f"  Warning: Could not delete {file}: {e}")
                logger.info(f"Removed {file_count} old songs")

                # if file_count > 0:
                #     self.cleanup_missing_files()

                #     wait_time = min(max(file_count // 2, 5), 20)
            #     time.sleep(wait_time)
        else:
            playlist_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(playlist_dir, 0o777)
            logger.info(f"Created directory: {playlist_dir}")

        song_ids: List[str] = []
        success_count = 0
        target_count = len(tracks)
        track_index = 0
        downloaded_tracks = []
        skipped_count = 0
        time.sleep(2)

        # Go through each song and either try to find it or download

        while success_count < target_count and track_index < len(tracks):
            track = tracks[track_index]
            track_index += 1

            artists = track.get("artists", [])
            artist = artists[0] if artists else "Unknown"
            title = track.get("title", "Unknown")

            # if self._is_artist_blocked(artist):
            #     logger.info(f"  Skipping blocked artist: {artist}")
            #     continue

            logger.info(
                f"\n[{success_count+1}/{target_count}] Attempting: {artist} - {title}"
            )

            existing_song_id = self.navidrome.search_navidrome_track(artist, title)

            if existing_song_id:
                logger.info("  Already in Navidrome library, skipping download")
                song_ids.append(existing_song_id)
                success_count += 1
                skipped_count += 1
                continue

            ytmusic_info = self.ytdlp.search_ytmusic_track(artist, title)

            if ytmusic_info:
                downloaded = self.ytdlp.download_track_ytmusic(
                    ytmusic_info["video_id"], playlist_dir, ytmusic_info
                )

                if downloaded:
                    logger.info("  Downloaded successfully")
                    success_count += 1
                    downloaded_tracks.append(downloaded)
                else:
                    logger.info("  Download failed, trying next backup track")
            else:
                logger.warning("  Not found on YouTube Music, saving to failed list")
                try:
                    with open(
                        Path(playlist_dir, "failed_tracks.csv"), "a", encoding="utf-8"
                    ) as f:
                        # ID, title, artist, timestamp, playlist name
                        timestamp = datetime.now(ZoneInfo("UTC")).isoformat()
                        f.write(
                            f"0, '{title}', '{artist}', '{timestamp}', '{playlist_name}'\n"
                        )
                except Exception as e:
                    logger.error(f"  Failed to write to failed_tracks.csv: {e}")

            time.sleep(1)

        logger.info(f"\nSuccessfully added {success_count}/{target_count} tracks")
        logger.info(f"  Downloaded: {len(downloaded_tracks)}")

        # Scan the playlist directory for new songs and add to Navidrome playlist
        if downloaded_tracks:
            new_song_ids = self.navidrome.scan_and_get_songs_from_directory(
                playlist_dir, downloaded_tracks
            )
            song_ids.extend(new_song_ids)

        # Update the Navidrome playlist with the new song IDs
        if song_ids:
            self.navidrome.update_playlist(playlist_id, song_ids)
            logger.info(
                f"Updated '{playlist_name}' Navidrome playlist with {len(song_ids)} tracks"
            )

    def syncPlaylists(self, playlist_names: Optional[List[str]] = None):

        # Sync specified playlists or all if none specified
        if playlist_names is None:
            playlist_names = list(self.csv_playlists.keys())

        for playlist_name in playlist_names:
            self.syncPlaylist(playlist_name)
