#!/usr/bin/env python3
import os
import sys
import json
import requests
import subprocess
import time
import hashlib
import re
import secrets
import fcntl
from pathlib import Path
from typing import List, Dict, Optional
from ytmusicapi import YTMusic
from datetime import datetime
from zoneinfo import ZoneInfo

import logging

from navidrome import Navidrome
from ytdlp import YTDLP

logger = logging.getLogger(__name__)


class CSVPlaylistSyncer:

    def __init__(self, navidrome: Navidrome, ytdlp: YTDLP):
        self.navidrome = navidrome
        self.ytdlp = ytdlp
        self.csv_playlists: Dict[str, List[Dict[str, str]]] = {}
        self.loadCSVFiles()
        pass

    def loadCSVFiles(self):
        # Load all csvs from /app/csv_playlists/

        self.csv_playlists: Dict[str, List[Dict[str, str]]] = {}
        csv_dir = Path("/app/csv_playlists")
        logger.info("Loading CSV playlists from: %s", csv_dir)
        if csv_dir.exists() and csv_dir.is_dir():
            for csv_file in csv_dir.glob("*.csv"):
                playlist_name = csv_file.stem
                try:
                    with open(csv_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    tracks = []
                    for line in lines:
                        parts = line.strip().split(",")
                        # If is csv title, then skip
                        if len(parts) >= 2 and parts[0].lower() in [
                            "id",
                            "title",
                            "artist",
                            "#",
                            "song",
                        ]:
                            continue
                        if len(parts) >= 3:
                            # Most formats include ID, Title, artist etc
                            # https://www.chosic.com/spotify-playlist-exporter/

                            # Remove quotes if present, strip whitespace
                            title = parts[1].replace('"', "").replace("'", "").strip()
                            artists = [
                                artist.strip()
                                for artist in parts[2]
                                .replace('"', "")
                                .replace("'", "")
                                .strip()
                                .split(",")
                            ]
                            tracks.append({"artists": artists, "title": title})
                            logger.info(
                                f"  Loaded track: {title} by {', '.join(artists)}"
                            )
                    self.csv_playlists[playlist_name] = tracks
                    logger.info(
                        f"Loaded CSV playlist '{playlist_name}' with {len(tracks)} tracks"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to load CSV playlist '{playlist_name}': {e}"
                    )
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

        # Clear old songs in the playlist directory (means not wanted)
        if playlist_dir.exists():
            logger.info(f"\nClearing old songs in {playlist_dir}")
            file_count = 0
            for file in playlist_dir.glob("*"):
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
                logger.info(f"  Already in Navidrome library, skipping download")
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
                    logger.info(f"  Downloaded successfully")
                    success_count += 1
                    downloaded_tracks.append(downloaded)
                else:
                    logger.info(f"  Download failed, trying next backup track")
            else:
                logger.info(f"  Not found on YouTube Music, trying next backup track")

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
