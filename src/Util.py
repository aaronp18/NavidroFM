from pathlib import Path
import re
from typing import Dict, Optional


import logging

import requests

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "")
    filename = " ".join(filename.split())
    return filename.strip()


def normalize_for_matching(text: str) -> str:
    """Normalize text for comparison"""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_artist_separators(
    artist_string: str, target_separator: str, protected: Optional[str] = None
) -> str:
    """Normalize various artist separators to the configured format.

    When *protected* is given (the primary artist name from the API), it is
    treated as an atomic token so that band names like "Invent, Animate" or
    "Author & Punisher" survive normalization intact.  Any feat. artists
    appended after the primary name are still normalized normally.
    """
    if not artist_string:
        return artist_string

    PLACEHOLDER = "\x00PRIMARY\x00"
    placeholder_active = False

    if protected:
        norm_string = re.sub(r"\s+", " ", artist_string).strip()
        norm_protected = re.sub(r"\s+", " ", protected).strip()
        if norm_string.lower().startswith(norm_protected.lower()):
            suffix = norm_string[len(norm_protected) :]
            artist_string = PLACEHOLDER + suffix
            placeholder_active = True

    unambiguous_patterns = [
        (r"\s+feat\.\s+", target_separator),
        (r"\s+ft\.\s+", target_separator),
        (r"\s+featuring\s+", target_separator),
        (r"\s+&\s+", target_separator),
        (r"\s+vs\.?\s+", target_separator),
        (r"\s*,\s*", target_separator),
        (r"\s*;\s*", target_separator),
        (r"\s*/\s*", target_separator),
    ]

    result = artist_string
    already_multi = False

    for pattern, replacement in unambiguous_patterns:
        new_result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        if new_result != result:
            already_multi = True
        result = new_result

    if already_multi:
        result = re.sub(r"\s+and\s+", target_separator, result, flags=re.IGNORECASE)

    if placeholder_active and protected:
        result = result.replace(PLACEHOLDER, protected.strip())

    return result.strip()


def set_metadata(file_path: Path, metadata: Dict):
    """Set metadata and clean comments"""
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, TPE1, TIT2, TALB, TDRC, TRCK, APIC, COMM  # type: ignore

        audio = MP3(file_path, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()

        if audio.tags is None:
            logger.warning(f"  Warning: audio.tags is still None after add_tags()")
        else:
            audio.tags.delall("COMM")

        artist_value = metadata.get("artist", "")
        artist_value = normalize_artist_separators(
            artist_value, "; ", protected=metadata.get("artist", "")
        )

        audio.tags["TPE1"] = TPE1(encoding=3, text=artist_value)  # type: ignore
        audio.tags["TIT2"] = TIT2(encoding=3, text=metadata.get("title", ""))  # type: ignore
        audio.tags["TALB"] = TALB(encoding=3, text=metadata.get("album", ""))  # type: ignore

        if metadata.get("year"):
            audio.tags["TDRC"] = TDRC(encoding=3, text=metadata["year"])  # type: ignore

        if metadata.get("track_number"):
            audio.tags["TRCK"] = TRCK(encoding=3, text=str(metadata["track_number"]))  # type: ignore

        cover_url = metadata.get("cover_url")
        if cover_url:
            try:
                response = requests.get(cover_url, timeout=10)
                if response.status_code == 200:
                    audio.tags["APIC"] = APIC(  # type: ignore
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=response.content,
                    )  # type: ignore
            except Exception as e:
                logger.warning(f"  Warning: Could not embed cover art: {e}")

        audio.save()

        audio = MP3(file_path, ID3=ID3)
        if audio.tags and audio.tags.getall("COMM"):
            logger.warning(f"  Warning: Comments still present after deletion")

        return artist_value

    except Exception as e:
        logger.warning(f"  Warning: Could not set metadata: {e}")
        return metadata.get("artist", "")
