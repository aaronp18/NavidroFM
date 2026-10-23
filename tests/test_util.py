"""Unit tests for the pure helpers in :mod:`Util`."""

import pytest

from Util import (
    normalize_artist_separators,
    normalize_for_matching,
    sanitize_filename,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AC/DC: Back in Black?", "ACDC Back in Black"),
        ("No|Illegal*Chars<>", "NoIllegalChars"),
        ('Quote" and \\ backslash', "Quote and backslash"),
        ("  Artist   -   Title  ", "Artist - Title"),
        ("", ""),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Don't Stop Me Now!", "dont stop me now"),
        ("AC/DC", "acdc"),
        ("  Foo   Bar  ", "foo bar"),
        ("Snake_Case", "snake_case"),
        ("Beyoncé", "beyoncé"),
        ("", ""),
    ],
)
def test_normalize_for_matching(raw, expected):
    assert normalize_for_matching(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("A & B", "A; B"),
        ("A feat. B", "A; B"),
        ("A ft. B", "A; B"),
        ("A featuring B", "A; B"),
        ("A, B", "A; B"),
        ("A;B", "A; B"),
        ("A / B", "A; B"),
        ("A vs. B", "A; B"),
        ("Single Artist", "Single Artist"),
        ("", ""),
    ],
)
def test_normalize_artist_separators(raw, expected):
    assert normalize_artist_separators(raw, "; ") == expected


def test_normalize_artist_separators_leaves_and_alone():
    """``and`` is only normalised once another separator proved a multi-artist tag."""
    assert normalize_artist_separators("Florence and the Machine", "; ") == (
        "Florence and the Machine"
    )


def test_normalize_artist_separators_protects_primary_artist():
    """Band names containing separators must survive metadata cleanup."""
    assert (
        normalize_artist_separators("Author & Punisher", "; ", protected="Author & Punisher")
        == "Author & Punisher"
    )
    assert (
        normalize_artist_separators(
            "Invent, Animate feat. Guest", "; ", protected="Invent, Animate"
        )
        == "Invent, Animate; Guest"
    )
