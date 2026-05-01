import os
from pathlib import Path
import re
import subprocess
import time
from typing import Dict, Optional
from ytmusicapi import YTMusic

from Util import (
    sanitize_filename,
    normalize_for_matching,
    normalize_artist_separators,
    set_metadata,
)

import logging

logger = logging.getLogger(__name__)


class YTDLP:
    def __init__(self):
        self.cookie_file = Path("/app/cookies/cookies.txt")

        try:
            self.ytmusic = YTMusic()
            logger.info("YouTube Music API initialized")
        except Exception as e:
            logger.error(f"Failed to initialize YouTube Music API: {e}")
            raise

        pass

    def search_ytmusic_track(self, artist: str, title: str) -> Optional[Dict]:
        """Search YouTube Music for a track with strict matching"""
        try:
            query = f"{artist} {title}"
            results = self.ytmusic.search(query, filter="songs", limit=10)

            if not results:
                return None

            norm_artist = normalize_for_matching(artist)
            norm_title = normalize_for_matching(title)

            best_match = None
            best_score = 0

            for result in results:
                result_artists = result.get("artists", [])
                if isinstance(result_artists, list):
                    result_artist = ", ".join(
                        [
                            a.get("name", "")
                            for a in result_artists
                            if isinstance(a, dict)
                        ]
                    )
                else:
                    result_artist = str(result_artists) if result_artists else ""

                result_title = result.get("title", "")

                norm_result_artist = normalize_for_matching(result_artist)
                norm_result_title = normalize_for_matching(result_title)

                artist_match = (
                    norm_artist in norm_result_artist
                    or norm_result_artist in norm_artist
                )
                title_match = (
                    norm_title in norm_result_title or norm_result_title in norm_title
                )

                if artist_match and title_match:
                    score = 0
                    if norm_artist == norm_result_artist:
                        score += 2
                    elif artist_match:
                        score += 1

                    if norm_title == norm_result_title:
                        score += 2
                    elif title_match:
                        score += 1

                    if score > best_score:
                        best_score = score
                        best_match = result

            if not best_match or best_score < 2:
                return None

            video_id = best_match.get("videoId")
            if not video_id:
                return None

            album_info = best_match.get("album")
            album_name = title
            album_id = None

            if isinstance(album_info, dict):
                album_name = album_info.get("name", album_name)
                album_id = album_info.get("id")

            year = ""
            track_number = 1

            if album_id:
                try:
                    album_details = self.ytmusic.get_album(album_id)
                    album_name = album_details.get("title", album_name)

                    release_date = album_details.get("releaseDate")
                    if release_date and isinstance(release_date, dict):
                        year = str(release_date.get("year", ""))
                    elif album_details.get("year"):
                        year = str(album_details.get("year"))

                    album_tracks = album_details.get("tracks", [])
                    norm_search_title = normalize_for_matching(title)

                    for idx, track in enumerate(album_tracks, start=1):
                        track_video_id = track.get("videoId", "")
                        track_title = track.get("title", "")
                        norm_track_title = normalize_for_matching(track_title)

                        if track_video_id == video_id:
                            track_number = idx
                            break
                        elif norm_track_title == norm_search_title:
                            track_number = idx
                            break

                except Exception as e:
                    logger.info(f"  Warning: Could not get album details: {e}")

            artists = best_match.get("artists", [])
            if isinstance(artists, list):
                artist_name = ", ".join(
                    [a.get("name", "") for a in artists if isinstance(a, dict)]
                )
            else:
                artist_name = artist

            thumbnails = best_match.get("thumbnails", [])
            cover_url = None
            if thumbnails and isinstance(thumbnails, list) and len(thumbnails) > 0:
                cover_url = thumbnails[-1].get("url", "")
                if cover_url and "=w" in cover_url:
                    cover_url = cover_url.split("=w")[0]

            return {
                "video_id": video_id,
                "title": best_match.get("title", title),
                "artist": artist_name or artist,
                "album": album_name,
                "year": year,
                "track_number": track_number,
                "cover_url": cover_url,
                "url": f"https://music.youtube.com/watch?v={video_id}",
            }

        except Exception as e:
            logger.info(f"  YouTube Music search error: {e}")
            return None

    def download_track_ytmusic(
        self,
        video_id: str,
        output_dir: Path,
        metadata: Dict,
        is_first_track: bool = False,
    ) -> Optional[Dict]:
        """Download track from YouTube Music and return metadata with sanitized artist"""
        try:
            if is_first_track:
                time.sleep(2)

            artist = metadata.get("artist", "Unknown")
            title = metadata.get("title", "Unknown")
            safe_filename = sanitize_filename(f"{artist} - {title}")

            url = f"https://music.youtube.com/watch?v={video_id}"

            cmd = [
                "yt-dlp",
                "-x",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "0",
                "--embed-thumbnail",
                "--no-embed-info-json",
                "--output",
                str(output_dir / f"{safe_filename}.%(ext)s"),
                "--format",
                "bestaudio",
                "--extractor-args",
                "youtube:player_client=default,mweb",
                "--sleep-interval",
                "2",
                "--no-update",
            ]

            if self.cookie_file.exists():
                cmd.extend(["--cookies", str(self.cookie_file)])
            else:
                logger.info(f"  Warning: Cookie file not found at {self.cookie_file}")

            cmd.append(url)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

            if result.returncode == 0:
                audio_file = output_dir / f"{safe_filename}.mp3"
                if audio_file.exists():
                    sanitized_artist = set_metadata(audio_file, metadata)
                    os.chmod(audio_file, 0o666)
                    return {
                        "artist": sanitized_artist,
                        "title": metadata.get("title", ""),
                    }
            else:
                error = result.stderr[:200] if result.stderr else "Unknown error"
                logger.info(f"  Download failed: {error}")
                return None

        except subprocess.TimeoutExpired:
            logger.info(f"  Timeout")
            return None
        except Exception as e:
            logger.info(f"  Error: {e}")
            return None
