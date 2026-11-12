"""Test reading the sessions that the Claude desktop app lists."""

import json
import pathlib

import pytest

from fogies.tools.claude_desktop import (
    DesktopSession,
    DesktopStatus,
    desktop_sessions,
    desktop_statuses,
    plan_resume,
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


def test_desktop_statuses_say_whether_the_app_lists_each_session() -> None:
    """Sessions with a transcript come first, then those the app lists without one."""
    recorded = {
        "listed": DesktopSession(session_id="listed", archived=False),
        "archived": DesktopSession(session_id="archived", archived=True),
        "no_transcript": DesktopSession(session_id="no_transcript", archived=False),
    }

    statuses = desktop_statuses(
        transcripts=["not_listed", "listed", "archived"], recorded=recorded
    )

    assert statuses == {
        "not_listed": DesktopStatus.NOT_LISTED,
        "listed": DesktopStatus.LISTED,
        "archived": DesktopStatus.ARCHIVED,
        "no_transcript": DesktopStatus.NO_HISTORY,
    }
    assert list(statuses)[-1] == "no_transcript"


def test_plan_resume_resumes_what_can_be_and_says_why_not_for_the_rest(
    tmp_path: pathlib.Path,
) -> None:
    """A session that is listed is left out, whether or not it could be resumed."""
    here = tmp_path / "here"
    here.mkdir()
    missing = tmp_path / "elsewhere"

    resumable, skipped = plan_resume(
        directories={
            "not_listed": str(here),
            "listed": str(here),
            "listed_no_directory": None,
            "not_listed_no_directory": None,
            "not_listed_directory_missing": str(missing),
        },
        listed=["listed", "listed_no_directory"],
    )

    assert resumable == {"not_listed": here}
    assert skipped == {
        "not_listed_no_directory": "has no recorded directory",
        "not_listed_directory_missing": "ran in '{}', which does not exist here".format(
            missing
        ),
    }
