"""Test reading the sessions that the Claude desktop app lists."""

import json
import pathlib
import subprocess

import pytest

from fogies.tools.claude_desktop import (
    DesktopSession,
    DesktopStatus,
    desktop_sessions,
    desktop_statuses,
    plan_resume,
    resume_each,
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


def test_resume_each_goes_on_after_a_session_that_cannot_be_resumed(
    tmp_path: pathlib.Path,
) -> None:
    """Each way that one can fail is returned with why, and the rest are resumed."""
    resumable = {
        "first": tmp_path,
        "exits_with_error": tmp_path,
        "directory_gone": tmp_path,
        "cannot_run": tmp_path,
        "last": tmp_path,
    }
    tried: list[str] = []

    def resume(session_id: str, cwd: pathlib.Path) -> None:
        assert cwd == tmp_path
        tried.append(session_id)
        if session_id == "exits_with_error":
            raise subprocess.CalledProcessError(1, ["claude"])
        if session_id == "directory_gone":
            raise ValueError("ran in a directory that does not exist here")
        if session_id == "cannot_run":
            raise PermissionError("access denied")

    resumed, failed = resume_each(resumable=resumable, resume=resume)

    assert tried == list(resumable)
    assert resumed == ["first", "last"]
    assert failed == {
        "exits_with_error": "Command '['claude']' returned non-zero exit status 1.",
        "directory_gone": "ran in a directory that does not exist here",
        "cannot_run": "access denied",
    }


def test_resume_each_does_not_hide_what_is_not_about_a_session(
    tmp_path: pathlib.Path,
) -> None:
    """A mistake in the code, as opposed to one session failing, is not swallowed."""

    def resume(session_id: str, cwd: pathlib.Path) -> None:
        _ = (session_id, cwd)
        raise KeyError("a bug")

    with pytest.raises(KeyError):
        _ = resume_each(resumable={"a": tmp_path}, resume=resume)
