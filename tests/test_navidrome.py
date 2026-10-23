"""Tests for :mod:`navidrome` that do not require a running server."""

import pytest

from navidrome import Navidrome


@pytest.mark.parametrize(
    "variable",
    ["NAVIDROME_URL", "NAVIDROME_USERNAME", "NAVIDROME_PASSWORD"],
)
def test_missing_credentials_raise_value_error(variable, monkeypatch):
    monkeypatch.setenv("NAVIDROME_URL", "http://localhost:4533")
    monkeypatch.setenv("NAVIDROME_USERNAME", "user")
    monkeypatch.setenv("NAVIDROME_PASSWORD", "pass")
    monkeypatch.delenv(variable)

    with pytest.raises(ValueError, match="NAVIDROME_"):
        Navidrome()
