"""Fixtures shared by the tests of the Claude tools."""

import pathlib

import pytest


@pytest.fixture
def temp_home(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Replace the home directory, where claude-sync looks for its files.

    CLAUDE_CONFIG_DIR is cleared too, as the Claude Agent SDK looks there instead
    of the home directory when it is set, and so would be working somewhere other
    than where the test is.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return home
