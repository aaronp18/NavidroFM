import argparse
import fcntl
import logging
import sys

from config import lock_file
from navidroFM import NavidroFM

logging.basicConfig(
    # filename="/app/logs/navidrofm.log",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def acquire_lock():
    """Try to acquire lock, return file descriptor or None"""
    try:
        lock_fd = open(lock_file(), "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except (IOError, OSError):
        return None


def release_lock(lock_fd):
    """Release the lock"""
    if lock_fd:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        except (IOError, OSError):
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="NavidroFM - Create Spotify-like playlists for Navidrome using ListenBrainz, LastFM or CSV files."
    )

    parser.add_argument(
        "type",
        choices=["recommended", "mix", "library", "exploration", "jams", "csv", "all"],
        help="Type of data source to use for playlist creation. Will only run if enabled in environment variables.",
    )
    args = parser.parse_args()

    lock_fd = acquire_lock()
    if not lock_fd:
        logger.error("Another instance of NavidroFM is already running. Exiting.")
        sys.exit(0)

    try:
        app = NavidroFM()

        logger.info(f"Running NavidroFM with data source: {args.type}")

        # Run CSV playlist syncer if requested
        if args.type == "csv" or args.type == "all":
            app.csv_syncer.syncPlaylists()

        # Run LastFM/ListenBrainz syncer if requested
        if (
            args.type in ["recommended", "mix", "library", "exploration", "jams"]
            or args.type == "all"
        ):
            app.runLastFMListenBrainz(args.type)

    except Exception as e:
        import traceback

        logger.error(f"Error: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        logger.info("NavidroFM run complete, releasing lock.")
        release_lock(lock_fd)
