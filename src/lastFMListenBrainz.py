"""A copy paste of existing logic"""

from datetime import datetime
import time
import os
from pathlib import Path
from typing import Dict, List, Optional

import logging
from zoneinfo import ZoneInfo

import requests

from navidrome import Navidrome
from ytdlp import YTDLP

logger = logging.getLogger(__name__)


class ListenBrainzLastFM:
    def __init__(self, navidrome: Navidrome, ytdlp: YTDLP):

        self.music_dir = Path("/music/navidrofm")
        self.navidrome = navidrome
        self.ytdlp = ytdlp

        self.lastfm_user = os.getenv("LASTFM_USERNAME")
        if not self.lastfm_user:
            raise ValueError("LASTFM_USERNAME environment variable is required")
        pass

        tz_name = os.getenv("TZ", "UTC")
        try:
            self.timezone = ZoneInfo(tz_name)
        except Exception:
            logger.warning(f"Warning: Invalid timezone '{tz_name}', using UTC")
            self.timezone = ZoneInfo("UTC")

        # Load artist blocklist from /app/blocklist.json if present.
        # Format: {"artists": ["Artist Name", "Another Artist"]}
        # Matching is case-insensitive.
        self.artist_blocklist: set = set()
        blocklist_path = Path("/app/blocklist.json")
        if blocklist_path.exists():
            try:
                import json as _json

                with open(blocklist_path) as _f:
                    _data = _json.load(_f)
                self.artist_blocklist = {
                    a.lower().strip() for a in _data.get("artists", [])
                }
                logger.info(
                    f"Loaded artist blocklist: {len(self.artist_blocklist)} entries"
                )
            except Exception as e:
                logger.error(f"Warning: Could not load blocklist.json: {e}")

        self.playlists = {
            "recommended": {
                "enabled": os.getenv("RECOMMENDED", "false").lower() == "true",
                "tracks": int(os.getenv("RECOMMENDED_TRACKS", "25")),
                "url": f"https://www.last.fm/player/station/user/{self.lastfm_user}/recommended",
                "name": "Discover Recommended",
                "dir": self.music_dir / "recommended",
                "schedule": os.getenv("RECOMMENDED_SCHEDULE", "0 4 * * 1"),
            },
            "mix": {
                "enabled": os.getenv("MIX", "false").lower() == "true",
                "tracks": int(os.getenv("MIX_TRACKS", "25")),
                "url": f"https://www.last.fm/player/station/user/{self.lastfm_user}/mix",
                "name": "Recommended Mix",
                "dir": self.music_dir / "mix",
                "schedule": os.getenv("MIX_SCHEDULE", "0 4 * * 1"),
            },
            "library": {
                "enabled": os.getenv("LIBRARY", "false").lower() == "true",
                "tracks": int(os.getenv("LIBRARY_TRACKS", "50")),
                "url": f"https://www.last.fm/player/station/user/{self.lastfm_user}/library",
                "name": "Library Mix",
                "dir": None,
                "schedule": os.getenv("LIBRARY_SCHEDULE", "0 4 * * 1"),
            },
        }

        self.listenbrainz_user = os.getenv("LZ_USERNAME")

        if self.listenbrainz_user:
            self.listenbrainz_playlists = {
                "exploration": {
                    "enabled": os.getenv("EXPLORATION", "false").lower() == "true",
                    "tracks": min(int(os.getenv("EXPLORATION_TRACKS", "25")), 50),
                    "name": "Weekly Exploration",
                    "dir": self.music_dir / "exploration",
                    "schedule": os.getenv("EXPLORATION_SCHEDULE", "0 4 * * 1"),
                    "playlist_type": "weekly-exploration",
                },
                "jams": {
                    "enabled": os.getenv("JAMS", "false").lower() == "true",
                    "tracks": min(int(os.getenv("JAMS_TRACKS", "25")), 50),
                    "name": "Weekly Jams",
                    "dir": self.music_dir / "jams",
                    "schedule": os.getenv("JAMS_SCHEDULE", "0 4 * * 1"),
                    "playlist_type": "weekly-jams",
                },
            }
        else:
            self.listenbrainz_playlists = {}

    def get_playlist_config(self, playlist_type: str) -> Optional[Dict]:
        """Get configuration for any playlist type (LastFM or ListenBrainz)"""
        if playlist_type in self.playlists:
            return self.playlists[playlist_type]
        elif playlist_type in self.listenbrainz_playlists:
            return self.listenbrainz_playlists[playlist_type]
        return None

    def fetch_listenbrainz_playlist_id(self, playlist_type: str) -> Optional[str]:
        """Get the current week's ListenBrainz playlist ID"""
        try:
            if not self.listenbrainz_user:
                logger.info("ListenBrainz username not configured")
                return None

            url = f"https://api.listenbrainz.org/1/user/{self.listenbrainz_user}/playlists/createdfor"

            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            playlists = data.get("playlists", [])
            if not playlists:
                logger.info("No playlists found for user")
                return None

            now = datetime.now()

            if playlist_type == "daily-jams":
                current_day = now.timetuple().tm_yday
            else:
                current_week = now.isocalendar()[1]

            for playlist_item in playlists:
                playlist = playlist_item.get("playlist", {})
                extension = playlist.get("extension", {}).get(
                    "https://musicbrainz.org/doc/jspf#playlist", {}
                )
                algorithm_metadata = extension.get("additional_metadata", {}).get(
                    "algorithm_metadata", {}
                )
                source_patch = algorithm_metadata.get("source_patch", "")

                if source_patch != playlist_type:
                    continue

                date_str = playlist.get("date")
                if date_str:
                    try:
                        playlist_date = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )

                        if playlist_type == "daily-jams":
                            playlist_day = playlist_date.timetuple().tm_yday
                            time_match = current_day == playlist_day  # type: ignore
                        else:
                            playlist_week = playlist_date.isocalendar()[1]
                            time_match = current_week == playlist_week  # type: ignore

                        if time_match:
                            identifier = playlist.get("identifier", "")
                            playlist_id = identifier.split("/")[-1]
                            logger.info(
                                f"Found {playlist_type} playlist: {playlist_id}"
                            )
                            return playlist_id
                    except Exception as e:
                        logger.info(f"Error parsing date for playlist: {e}")
                        continue

            logger.info(f"No current {playlist_type} playlist found")
            return None

        except Exception as e:
            logger.info(f"Error fetching ListenBrainz playlists: {e}")
            return None

    def fetch_listenbrainz_tracks(
        self, playlist_id: str, num_tracks: int
    ) -> List[Dict]:
        """Fetch tracks from a ListenBrainz playlist"""
        try:
            url = f"https://api.listenbrainz.org/1/playlist/{playlist_id}"

            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            playlist = data.get("playlist", {})
            tracks = playlist.get("track", [])

            if not tracks:
                logger.info("No tracks found in playlist")
                return []

            converted_tracks = []
            for track in tracks:
                title = track.get("title", "")
                artist = track.get("creator", "")
                album = track.get("album", "")

                if not title or not artist:
                    continue

                extension = track.get("extension", {}).get(
                    "https://musicbrainz.org/doc/jspf#track", {}
                )
                additional_metadata = extension.get("additional_metadata", {})
                artists_list = additional_metadata.get("artists", [])

                if len(artists_list) > 1:
                    artist_names = [
                        a.get("artist_credit_name", "")
                        for a in artists_list
                        if a.get("artist_credit_name")
                    ]
                    if artist_names:
                        artist = ", ".join(artist_names)

                converted_tracks.append(
                    {"name": title, "artists": [{"name": artist}], "album": album}
                )
            return converted_tracks

        except Exception as e:
            logger.info(f"Error fetching ListenBrainz playlist tracks: {e}")
            return []

    def fetch_lastfm_tracks(self, url: str, num_tracks: int) -> List[Dict]:
        """Fetch tracks from LastFM JSON endpoint with backup songs"""
        backup_multiplier = 3
        fetch_count = num_tracks * backup_multiplier

        logger.info(
            f"Fetching {fetch_count} tracks from LastFM (need {num_tracks}, extras as backup)"
        )

        all_tracks = []
        seen_ids = set()
        max_attempts = 20
        attempts = 0

        while len(all_tracks) < fetch_count and attempts < max_attempts:
            attempts += 1
            logger.info(f"  Query {attempts}: Fetching more tracks...")

            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()

                tracks = data.get("playlist", [])
                if not tracks:
                    logger.info("  No more tracks available from API")
                    break

                new_tracks = 0
                for track in tracks:
                    track_name = track.get("name", "")
                    artists = track.get("artists", [])
                    artist_name = artists[0].get("name", "") if artists else ""
                    track_id = f"{artist_name}:{track_name}"

                    if track_id not in seen_ids and track_name and artist_name:
                        seen_ids.add(track_id)
                        all_tracks.append(track)
                        new_tracks += 1

                        if len(all_tracks) >= fetch_count:
                            break

                logger.info(
                    f"  Added {new_tracks} new tracks (total: {len(all_tracks)}/{fetch_count})"
                )

                if new_tracks == 0:
                    logger.info("  API is repeating tracks, stopping")
                    break

                if len(all_tracks) < fetch_count:
                    time.sleep(1)

            except Exception as e:
                logger.info(f"  Error fetching LastFM data: {e}")
                break

        logger.info(f"Collected {len(all_tracks)} tracks ({num_tracks} + backups)")
        return all_tracks

    def fetch_tracks_for_playlist(self, playlist_type: str, config: Dict) -> List[Dict]:
        """Fetch tracks for any playlist type"""
        if playlist_type in self.playlists:
            return self.fetch_lastfm_tracks(config["url"], config["tracks"])
        elif playlist_type in self.listenbrainz_playlists:
            playlist_id = self.fetch_listenbrainz_playlist_id(config["playlist_type"])
            if not playlist_id:
                logger.info("Could not find current week's playlist")
                return []
            return self.fetch_listenbrainz_tracks(playlist_id, config["tracks"])
        return []

    def _is_artist_blocked(self, artist: str) -> bool:
        """Return True if the artist matches any entry in the blocklist."""
        if not self.artist_blocklist:
            return False
        return artist.lower().strip() in self.artist_blocklist

    def cleanup_missing_files(self):
        """Remove orphaned playlist entries after deleting files"""
        try:

            response = self.navidrome.make_subsonic_request("getPlaylists")
            playlists = (
                response.get("subsonic-response", {})
                .get("playlists", {})
                .get("playlist", [])
            )

            if isinstance(playlists, dict):
                playlists = [playlists]

            managed_names = [config["name"] for config in self.playlists.values()]
            if self.listenbrainz_playlists:
                managed_names.extend(
                    [config["name"] for config in self.listenbrainz_playlists.values()]
                )

            for playlist in playlists:
                if playlist["name"] in managed_names:
                    playlist_id = playlist["id"]
                    try:
                        self.navidrome.make_subsonic_request(
                            "createPlaylist", {"playlistId": playlist_id}
                        )
                    except Exception as e:
                        logger.info(f"    Warning: Could not clear playlist: {e}")

        except Exception as e:
            logger.info(f"Warning: Could not cleanup playlists: {e}")

    def sync_playlist(self, playlist_type: str):
        """Unified sync function for both LastFM and ListenBrainz playlists"""
        config = self.get_playlist_config(playlist_type)

        if not config:
            logger.info(f"Unknown playlist type: {playlist_type}")
            return

        if not config["enabled"]:
            logger.info(f"Playlist {playlist_type} is disabled, skipping")
            return

        logger.info(f"\n{'='*60}")
        logger.info(f"Syncing {config['name']}")
        logger.info(f"{'='*60}")

        tracks = self.fetch_tracks_for_playlist(playlist_type, config)

        if not tracks:
            logger.info("No tracks found, aborting")
            return

        playlist_id = self.navidrome.get_navidrome_playlist_id(config["name"])
        if not playlist_id:
            logger.info("Failed to get/create playlist")
            return

        song_ids = []
        downloaded_tracks = []

        if playlist_type == "library":
            logger.info("\nBuilding library playlist from existing songs...")
            success_count = 0
            target_count = config["tracks"]
            track_index = 0

            while success_count < target_count and track_index < len(tracks):
                track = tracks[track_index]
                track_index += 1

                artists = track.get("artists", [])
                artist = artists[0].get("name", "") if artists else ""
                title = track.get("name", "")

                if not artist or not title:
                    continue

                if self._is_artist_blocked(artist):
                    logger.info(f"  Skipping blocked artist: {artist}")
                    continue

                song_id = self.navidrome.search_navidrome_track(artist, title)
                if song_id:
                    song_ids.append(song_id)
                    success_count += 1
                    logger.info(f"  Found in library")
                else:
                    logger.info(f"  Not found in library, trying next backup track")

        else:
            playlist_dir = config["dir"]

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

                if file_count > 0:
                    self.cleanup_missing_files()

                    wait_time = min(max(file_count // 2, 5), 20)
                    time.sleep(wait_time)
            else:
                playlist_dir.mkdir(parents=True, exist_ok=True)
                os.chmod(playlist_dir, 0o777)
                logger.info(f"Created directory: {playlist_dir}")

            logger.info(
                f"\nProcessing {config['tracks']} tracks (total available with backups: {len(tracks)})"
            )
            success_count = 0
            target_count = config["tracks"]
            track_index = 0
            skipped_count = 0
            time.sleep(2)

            while success_count < target_count and track_index < len(tracks):
                track = tracks[track_index]
                track_index += 1

                artists = track.get("artists", [])
                artist = artists[0].get("name", "Unknown") if artists else "Unknown"
                title = track.get("name", "Unknown")

                if self._is_artist_blocked(artist):
                    logger.info(f"  Skipping blocked artist: {artist}")
                    continue

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
                    logger.info(
                        f"  Not found on YouTube Music, trying next backup track"
                    )

                time.sleep(1)

            logger.info(f"\nSuccessfully added {success_count}/{target_count} tracks")
            logger.info(f"  Downloaded: {len(downloaded_tracks)}")

            if downloaded_tracks:
                new_song_ids = self.navidrome.scan_and_get_songs_from_directory(
                    playlist_dir, downloaded_tracks
                )
                song_ids.extend(new_song_ids)

        logger.info("")
        self.navidrome.update_playlist(playlist_id, song_ids)
        logger.info(f"\n{'='*60}")
        logger.info(f"Completed syncing {config['name']}")
        if playlist_type != "library":
            logger.info(
                f"  Downloaded: {len(downloaded_tracks) if 'downloaded_tracks' in locals() else 'N/A'}"
            )
        logger.info(f"  In Navidrome: {len(song_ids)}")
        logger.info(f"{'='*60}\n")

    def get_next_cron_schedule(self) -> Optional[str]:
        """Get the schedule for the next enabled playlist"""

        sync_schedule = os.getenv("SYNC_SCHEDULE")
        if sync_schedule:
            return sync_schedule

        # Fallback in case of weird failure
        for playlist_type in ["recommended", "mix", "library"]:
            config = self.playlists[playlist_type]
            if config["enabled"]:
                return config["schedule"]
        return None

    def get_current_time(self) -> str:
        """Get current time in the configured timezone"""
        return datetime.now(self.timezone).strftime("%Y-%m-%d %H:%M:%S %Z")
