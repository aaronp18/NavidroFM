import logging
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from csvPlaylistSyncer import CSVPlaylistSyncer
from lastFMListenBrainz import ListenBrainzLastFM

from navidrome import Navidrome
from ytdlp import YTDLP

logger = logging.getLogger(__name__)


class NavidroFM:
    def __init__(self):

        logger.info("Starting NavidroFM application")

        self.navidrome = Navidrome()
        self.ytdlp = YTDLP()
        self.csv_syncer = CSVPlaylistSyncer(self.navidrome, self.ytdlp)

        self.lastFMListenBrainz = ListenBrainzLastFM(self.navidrome, self.ytdlp)

        tz_name = os.getenv("TZ", "UTC")
        try:
            self.timezone = ZoneInfo(tz_name)
        except Exception:
            logger.warning(f"[MAIN] Warning: Invalid timezone '{tz_name}', using UTC")
            self.timezone = ZoneInfo("UTC")

        self.loadBlockedArtists()

        pass

    def loadBlockedArtists(self):
        #         Load artist blocklist from /app/blocklist.json if present.
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
                logger.warn(f"Warning: Could not load blocklist.json: {e}")

    def runLastFMListenBrainz(self, playlist_type: str):
        if playlist_type == "all":
            for ptype in ["recommended", "mix", "library"]:
                self.lastFMListenBrainz.sync_playlist(ptype)
            for ptype in ["exploration", "jams"]:
                self.lastFMListenBrainz.sync_playlist(ptype)
        else:
            self.lastFMListenBrainz.sync_playlist(playlist_type)

        schedule = self.lastFMListenBrainz.get_next_cron_schedule()
        if schedule:
            logger.info(f"\n{'='*60}")
            logger.info(
                f"Sync completed at {self.lastFMListenBrainz.get_current_time()}"
            )
            logger.info(f"Next sync scheduled: {schedule}")
            logger.info(f"{'='*60}\n")
