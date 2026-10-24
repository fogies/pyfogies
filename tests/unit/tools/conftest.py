"""Fixtures shared by the tests of tools."""

import pathlib

import pytest


@pytest.fixture
def temp_home(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Replace the home directory, where claude-sync looks for its files."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home
