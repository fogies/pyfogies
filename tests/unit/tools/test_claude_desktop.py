"""Test reading the sessions that the Claude desktop app lists."""

import json
import pathlib

import pytest

from fogies.tools.claude_desktop import (
    DesktopSession,
    desktop_sessions,
)


def _write_record(directory: pathlib.Path, name: str, record: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    _ = (directory / name).write_text(json.dumps(record), encoding="utf-8")


def test_desktop_sessions_are_read_from_any_depth(tmp_path: pathlib.Path) -> None:
    """Records are in a directory for an account and one for an organization."""
    deep = tmp_path / "account" / "organization"
    _write_record(
        deep,
        "local_a.json",
        {"cliSessionId": "a", "isArchived": False, "title": "First"},
    )
    _write_record(deep, "local_b.json", {"cliSessionId": "b", "isArchived": True})
    # A record that has not yet been given a session to resume.
    _write_record(deep, "local_c.json", {"title": "New"})

    assert desktop_sessions(directory=tmp_path) == {
        "a": DesktopSession(session_id="a", archived=False, title="First"),
        "b": DesktopSession(session_id="b", archived=True, title=None),
    }


def test_desktop_sessions_skips_records_that_cannot_be_read(
    tmp_path: pathlib.Path,
) -> None:
    _write_record(tmp_path, "local_a.json", {"cliSessionId": "a"})
    _ = (tmp_path / "local_bad.json").write_text("{not json", encoding="utf-8")
    _write_record(tmp_path, "local_list.json", ["cliSessionId"])
    _write_record(tmp_path, "local_number.json", {"cliSessionId": 5})

    assert list(desktop_sessions(directory=tmp_path) or {}) == ["a"]


def test_desktop_sessions_with_none_recorded(tmp_path: pathlib.Path) -> None:
    """The app being used and having no sessions is not the app being absent."""
    assert desktop_sessions(directory=tmp_path) == {}
    assert desktop_sessions(directory=tmp_path / "missing") is None


def test_desktop_sessions_in_a_format_that_is_not_recognised(
    tmp_path: pathlib.Path,
) -> None:
    """Records that none can be read from are not the same as no sessions."""
    _write_record(tmp_path, "local_a.json", {"sessionId": "a"})
    _write_record(tmp_path, "local_b.json", {"id": "b"})

    with pytest.raises(ValueError, match="not recognised"):
        _ = desktop_sessions(directory=tmp_path)
