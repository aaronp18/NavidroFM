"""Tests for CSV playlist parsing (``csvPlaylistSyncer.parse_csv_playlist``)."""

import pytest

from csvPlaylistSyncer import CSVPlaylistSyncer, parse_csv_playlist

CHOSIC_STYLE = """ID,Title,Artist
1,Plain Title,"Artist One"
2,"Song, With Comma","Artist A, Artist B"
3,Solo,Artist
"""

SPOTIFY_STYLE = """#,Song,Artist,BPM,Camelot,Energy
1,"White Noise","Holly Humberstone",115,10B,84
2,"Why Am I Here","Presley Regier",123,4B,95
"""


def _write(tmp_path, content, name="playlist.csv"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_parses_title_and_artists(tmp_path):
    tracks = parse_csv_playlist(_write(tmp_path, CHOSIC_STYLE))
    assert tracks == [
        {"artists": ["Artist One"], "title": "Plain Title"},
        {"artists": ["Artist A", "Artist B"], "title": "Song, With Comma"},
        {"artists": ["Artist"], "title": "Solo"},
    ]


def test_skips_header_and_ignores_extra_columns(tmp_path):
    tracks = parse_csv_playlist(_write(tmp_path, SPOTIFY_STYLE))
    assert [t["title"] for t in tracks] == ["White Noise", "Why Am I Here"]
    assert tracks[0]["artists"] == ["Holly Humberstone"]


def test_blank_lines_and_short_rows_are_skipped(tmp_path):
    content = "ID,Title,Artist\n\n1,Real Song,Real Artist\nonly-one-column\n"
    tracks = parse_csv_playlist(_write(tmp_path, content))
    assert tracks == [{"artists": ["Real Artist"], "title": "Real Song"}]


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_csv_playlist(tmp_path / "does-not-exist.csv")


def test_syncer_loads_every_csv_sorted(monkeypatch, tmp_path):
    (tmp_path / "B Playlist.csv").write_text("ID,Title,Artist\n1,Two,Artist Two\n")
    (tmp_path / "A Playlist.csv").write_text("ID,Title,Artist\n1,One,Artist One\n")
    (tmp_path / "notes.txt").write_text("ignored")
    monkeypatch.setenv("NAVIDROFM_CSV_DIR", str(tmp_path))

    syncer = CSVPlaylistSyncer(navidrome=object(), ytdlp=object())

    assert list(syncer.csv_playlists) == ["A Playlist", "B Playlist"]
    assert syncer.csv_playlists["A Playlist"] == [
        {"artists": ["Artist One"], "title": "One"}
    ]


def test_syncer_handles_missing_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("NAVIDROFM_CSV_DIR", str(tmp_path / "missing"))
    syncer = CSVPlaylistSyncer(navidrome=object(), ytdlp=object())
    assert syncer.csv_playlists == {}


def test_syncer_reads_remove_old_tracks_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("NAVIDROFM_CSV_DIR", str(tmp_path))
    monkeypatch.setenv("REMOVE_OLD_TRACKS", "true")
    syncer = CSVPlaylistSyncer(navidrome=object(), ytdlp=object())
    assert syncer.removeOldTracks is True
