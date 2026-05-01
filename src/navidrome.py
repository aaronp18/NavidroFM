import hashlib
import os
import logging
from pathlib import Path
import secrets
import time
from typing import Dict, List, Optional, Union

import requests

logger = logging.getLogger(__name__)


class Navidrome:
    def __init__(self):
        self.navidrome_url = os.getenv("NAVIDROME_URL", "").rstrip("/")
        self.navidrome_user = os.getenv("NAVIDROME_USERNAME")
        self.navidrome_pass = os.getenv("NAVIDROME_PASSWORD")
        self.music_dir = Path("/music/navidrofm")

        if not all([self.navidrome_url, self.navidrome_user, self.navidrome_pass]):
            raise ValueError(
                "NAVIDROME_URL, NAVIDROME_USERNAME, and NAVIDROME_PASSWORD are required"
            )

        logger.info(f"[NAVIDROME]Connecting to Navidrome at {self.navidrome_url}...")

        salt = secrets.token_hex(8)
        token = hashlib.md5(f"{self.navidrome_pass}{salt}".encode()).hexdigest()

        self.subsonic_params = {
            "u": self.navidrome_user,
            "t": token,
            "s": salt,
            "v": "1.16.1",
            "c": "lastfm-sync",
            "f": "json",
        }

        try:
            response = self.make_subsonic_request("ping")
            subsonic_response = response.get("subsonic-response", {})
            status = subsonic_response.get("status")

            if status == "ok":
                logger.info("Successfully connected to Navidrome")
            else:
                error = subsonic_response.get("error", {})
                error_message = error.get("message", "unknown error")
                raise ConnectionError(f"Navidrome auth failed: {error_message}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Navidrome: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Navidrome: {e}")
            raise

    def make_subsonic_request(
        self, endpoint: str, extra_params: Optional[Dict[str, Union[str, int]]] = None
    ) -> Dict:
        """Make a request to the Subsonic API"""
        params = self.subsonic_params.copy()
        if extra_params:
            params.update(extra_params)

        url = f"{self.navidrome_url}/rest/{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_navidrome_playlist_id(self, playlist_name: str) -> Optional[str]:
        """Get or create playlist from the given name returning the playlist ID"""
        try:
            logger.info(f"Fetching playlists from Navidrome...")
            response = self.make_subsonic_request("getPlaylists")

            playlists = (
                response.get("subsonic-response", {})
                .get("playlists", {})
                .get("playlist", [])
            )

            if isinstance(playlists, dict):
                playlists = [playlists]

            for pl in playlists:
                if pl["name"] == playlist_name:
                    logger.info(
                        f"Found existing playlist: {playlist_name} (ID: {pl['id']})"
                    )
                    return pl["id"]

            logger.info(f"Creating new playlist: {playlist_name}")
            response = self.make_subsonic_request(
                "createPlaylist", {"name": playlist_name}
            )
            playlist = response.get("subsonic-response", {}).get("playlist", {})
            playlist_id = playlist.get("id")

            if playlist_id:
                logger.info(f"Created playlist: {playlist_name} (ID: {playlist_id})")

            return playlist_id
        except Exception as e:
            import traceback

            logger.error(f"Error managing playlist: {e}")
            traceback.print_exc()
            return None

    def search_navidrome_track(self, artist: str, title: str) -> Optional[str]:
        """Search for a track in Navidrome"""
        try:
            query = f"{artist} {title}"
            response = self.make_subsonic_request(
                "search3",
                {"query": query, "artistCount": 0, "albumCount": 0, "songCount": 5},
            )

            songs = (
                response.get("subsonic-response", {})
                .get("searchResult3", {})
                .get("song", [])
            )
            if songs:
                if isinstance(songs, dict):
                    songs = [songs]
                return songs[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Error searching for track: {e}")
            return None

    def get_songs_by_path_pattern(self, path_pattern: str) -> List[str]:
        """Get all song IDs matching a path pattern"""
        try:
            response = self.make_subsonic_request(
                "search3",
                {
                    "query": path_pattern,
                    "artistCount": 0,
                    "albumCount": 0,
                    "songCount": 500,
                },
            )

            songs = (
                response.get("subsonic-response", {})
                .get("searchResult3", {})
                .get("song", [])
            )

            if isinstance(songs, dict):
                songs = [songs]

            song_ids = []
            for song in songs:
                song_path = song.get("path", "")
                if path_pattern in song_path:
                    song_ids.append(song.get("id"))

            return song_ids
        except Exception as e:
            logger.error(f"Error getting songs by path: {e}")
            return []

    def scan_and_get_songs_from_directory(
        self, directory: Path, downloaded_tracks: List[Dict]
    ) -> List[str]:
        """Scan library and find songs by searching for each downloaded track. Returns list of found song IDs."""
        song_ids = []

        try:
            if not downloaded_tracks:
                logger.info("No new tracks downloaded, skipping scan")
                return song_ids

            try:
                relative_path = directory.relative_to("/music")
                library_id = os.getenv("NAVIDROME_LIBRARY_ID", "1")
                target_path = f"{library_id}:{relative_path}"

                logger.info(
                    f"Triggering selective Navidrome scan for {len(downloaded_tracks)} new tracks..."
                )

                self.make_subsonic_request(
                    "startScan", {"fullScan": "false", "target": target_path}
                )
            except ValueError:
                logger.info(
                    f"Warning: Could not determine relative path for {directory}, falling back to full scan"
                )
                logger.info(
                    f"Triggering Navidrome library scan for {len(downloaded_tracks)} new tracks..."
                )
                self.make_subsonic_request("startScan", {"fullScan": "false"})

            logger.info("Waiting for scan to complete...")
            scan_time = 0

            while True:
                time.sleep(2)
                scan_time += 2

                try:
                    status = self.make_subsonic_request("getScanStatus")
                    scan_status = status.get("subsonic-response", {}).get(
                        "scanStatus", {}
                    )
                    scanning = scan_status.get("scanning", False)
                    count = scan_status.get("count", 0)

                    if not scanning:
                        logger.info(
                            f"Scan completed after {scan_time}s ({count} items processed)"
                        )
                        break

                    if scan_time % 20 == 0:
                        logger.info(
                            f"  Still scanning... ({scan_time}s, {count} items so far)"
                        )

                except Exception as e:
                    if scan_time % 30 == 0:
                        logger.warning(f"  Warning: Could not check scan status: {e}")
                    pass

            wait_time = min(max(len(downloaded_tracks), 5), 30)
            logger.info(f"Waiting {wait_time}s for indexing to complete...")
            time.sleep(wait_time)

            logger.info(
                f"\nSearching for {len(downloaded_tracks)} downloaded tracks in Navidrome..."
            )

            not_found_tracks = []

            for i, track_info in enumerate(downloaded_tracks, 1):
                artist = track_info.get("artist", "")
                title = track_info.get("title", "")

                if not artist or not title:
                    continue

                try:
                    query = f"{artist} {title}"
                    response = self.make_subsonic_request(
                        "search3",
                        {
                            "query": query,
                            "artistCount": 0,
                            "albumCount": 0,
                            "songCount": 10,
                        },
                    )

                    songs = (
                        response.get("subsonic-response", {})
                        .get("searchResult3", {})
                        .get("song", [])
                    )
                    if isinstance(songs, dict):
                        songs = [songs]

                    if songs:
                        song_id = songs[0].get("id")
                        if song_id:
                            song_ids.append(song_id)
                        else:
                            logger.info(
                                f"  [{i}/{len(downloaded_tracks)}] No valid song ID for: {artist} - {title}"
                            )
                            not_found_tracks.append(track_info)
                    else:
                        logger.info(
                            f"  [{i}/{len(downloaded_tracks)}] Not found: {artist} - {title}"
                        )
                        not_found_tracks.append(track_info)

                except Exception as e:
                    logger.error(
                        f"  [{i}/{len(downloaded_tracks)}] Search error for {artist} - {title}: {e}"
                    )
                    not_found_tracks.append(track_info)

            if not_found_tracks:
                retry_wait = min(len(not_found_tracks) * 2, 30)
                logger.info(
                    f"\n{len(not_found_tracks)} tracks not found, waiting {retry_wait}s and retrying..."
                )
                time.sleep(retry_wait)

                for track_info in not_found_tracks:
                    artist = track_info.get("artist", "")
                    title = track_info.get("title", "")

                    if not artist or not title:
                        continue

                    try:
                        query = f"{artist} {title}"
                        response = self.make_subsonic_request(
                            "search3",
                            {
                                "query": query,
                                "artistCount": 0,
                                "albumCount": 0,
                                "songCount": 10,
                            },
                        )

                        songs = (
                            response.get("subsonic-response", {})
                            .get("searchResult3", {})
                            .get("song", [])
                        )
                        if isinstance(songs, dict):
                            songs = [songs]

                        if songs:
                            song_id = songs[0].get("id")
                            if song_id:
                                song_ids.append(song_id)
                                logger.info(f"  Found on retry: {artist} - {title}")

                    except Exception as e:
                        logger.error(
                            f"  Retry search error for {artist} - {title}: {e}"
                        )

            logger.info(
                f"\nFound {len(song_ids)}/{len(downloaded_tracks)} tracks in Navidrome"
            )
            return song_ids

        except Exception as e:
            import traceback

            logger.error(f"Error scanning and searching tracks: {e}")
            traceback.print_exc()
            return []

    def update_playlist(self, playlist_id: str, song_ids: List[str]):
        """Update playlist with songs"""
        try:
            logger.info(f"Updating playlist with {len(song_ids)} tracks...")

            if song_ids:
                self.make_subsonic_request(
                    "createPlaylist", {"playlistId": playlist_id, "songId": song_ids}
                )
                logger.info(f"Updated playlist with {len(song_ids)} tracks")
            else:
                self.make_subsonic_request(
                    "createPlaylist", {"playlistId": playlist_id}
                )
                logger.info("Cleared playlist (no songs to add)")
        except Exception as e:
            import traceback

            logger.error(f"Error updating playlist: {e}")
            traceback.print_exc()
