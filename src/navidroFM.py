import logging
import os
from zoneinfo import ZoneInfo

from blocklist import load_blocked_artists
from config import music_dir
from csvPlaylistSyncer import CSVPlaylistSyncer
from lastFMListenBrainz import ListenBrainzLastFM
from navidrome import Navidrome
from ytdlp import YTDLP

logger = logging.getLogger(__name__)


class NavidroFM:
    def __init__(self):

        logger.info("Starting NavidroFM application")
        logger.info("Music directory: %s", music_dir())

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

    def loadBlockedArtists(self):
        """Load the optional artist blocklist (``NAVIDROFM_BLOCKLIST_FILE``)."""
        self.artist_blocklist: set = load_blocked_artists()

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
