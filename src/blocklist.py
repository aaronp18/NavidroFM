"""Artist blocklist loading.

The blocklist format is ``{"artists": ["Artist Name", "Another Artist"]}``.
Matching is case-insensitive and happens in the syncers, not here.
"""

import json
import logging
from pathlib import Path

from config import blocklist_file

logger = logging.getLogger(__name__)


def load_blocked_artists(path: Path | None = None) -> set:
    """Return the set of lower-cased artist names to skip.

    A missing file is not an error -- the blocklist is optional.
    """
    path = path or blocklist_file()
    if not path.exists():
        return set()

    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        blocked = {a.lower().strip() for a in data.get("artists", [])}
        logger.info("Loaded artist blocklist: %s entries", len(blocked))
        return blocked
    except Exception as e:
        logger.warning("Warning: Could not load blocklist.json: %s", e)
        return set()
