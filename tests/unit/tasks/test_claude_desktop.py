"""Test the tasks for the sessions that the Claude desktop app lists."""

import contextlib
import pathlib
from collections.abc import Generator

import pytest
from invoke.context import Context

from fogies.tasks.claude_desktop import get_task_resume, get_task_sessions
from fogies.tools.claude_desktop import DesktopSession

from .conftest import WriteSession

_LISTED = "11111111-0000-4000-8000-000000000001"
_ARCHIVED = "22222222-0000-4000-8000-000000000002"
_NOT_LISTED = "33333333-0000-4000-8000-000000000003"
_NO_DIRECTORY = "44444444-0000-4000-8000-000000000004"
_NOT_HERE = "55555555-0000-4000-8000-000000000005"
_GONE = "66666666-0000-4000-8000-000000000006"


class _FakeClaudeCode:
    """Records the sessions resumed, instead of opening the app."""

    resumed: list[str]

    def __init__(self) -> None:
        self.resumed = []

    def resume_in_desktop(self, *, session_id: str, cwd: pathlib.Path) -> None:
        _ = cwd
        self.resumed.append(session_id)


@pytest.fixture
def sessions(write_session: WriteSession, tmp_path: pathlib.Path) -> None:
    """Sessions with transcripts here, in each state the app may have them in."""
    for session_id in (_LISTED, _ARCHIVED, _NOT_LISTED):
        _ = write_session(session_id, tmp_path)
    # Not able to be resumed here, and so not resumed.
    _ = write_session(_NO_DIRECTORY, None)
    _ = write_session(_NOT_HERE, tmp_path / "elsewhere")


@pytest.fixture
def desktop(monkeypatch: pytest.MonkeyPatch) -> dict[str, DesktopSession]:
    """What the app lists: two sessions here, and one that has no transcript."""
    listed = {
        _LISTED: DesktopSession(session_id=_LISTED, archived=False, title="Open"),
        _ARCHIVED: DesktopSession(session_id=_ARCHIVED, archived=True, title=None),
        _GONE: DesktopSession(session_id=_GONE, archived=False, title="Lost"),
    }
    monkeypatch.setattr("fogies.tasks.claude_desktop.desktop_sessions", lambda: listed)
    return listed


@pytest.fixture
def claude_code(monkeypatch: pytest.MonkeyPatch) -> _FakeClaudeCode:
    fake = _FakeClaudeCode()

    @contextlib.contextmanager
    def fake_claude_code(
        *, binary_cache_path: pathlib.Path
    ) -> Generator[_FakeClaudeCode]:
        _ = binary_cache_path
        yield fake

    monkeypatch.setattr("fogies.tasks.claude_desktop.claude_code", fake_claude_code)
    return fake


@pytest.mark.usefixtures("sessions", "desktop")
def test_sessions_shows_what_the_app_lists(capsys: pytest.CaptureFixture[str]) -> None:
    _ = get_task_sessions()(Context())

    lines = capsys.readouterr().out.splitlines()
    for session_id, status in {
        _LISTED: "listed",
        _ARCHIVED: "archived",
        _NOT_LISTED: "not listed",
        _GONE: "no history",
    }.items():
        (line,) = [line for line in lines if session_id in line]
        assert line.startswith(status + " ")


def test_sessions_without_the_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fogies.tasks.claude_desktop.desktop_sessions", lambda: None)

    with pytest.raises(ValueError, match="not found"):
        _ = get_task_sessions()(Context())


@pytest.mark.usefixtures("sessions", "desktop")
def test_resume_all_resumes_what_is_not_listed(
    claude_code: _FakeClaudeCode,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Not those listed, archived ones included, nor those that can't be here."""
    _ = get_task_resume(binary_cache_path=tmp_path)(Context(), all_=True)

    assert claude_code.resumed == [_NOT_LISTED]
    out = capsys.readouterr().out
    assert "Skipping {}".format(_NO_DIRECTORY) in out
    assert "Skipping {}".format(_NOT_HERE) in out


def test_resume_all_without_the_app(
    monkeypatch: pytest.MonkeyPatch,
    claude_code: _FakeClaudeCode,
    tmp_path: pathlib.Path,
) -> None:
    """Without knowing what is listed, all of them are not resumed."""
    monkeypatch.setattr("fogies.tasks.claude_desktop.desktop_sessions", lambda: None)

    with pytest.raises(ValueError, match="not found"):
        _ = get_task_resume(binary_cache_path=tmp_path)(Context(), all_=True)

    assert claude_code.resumed == []


@pytest.mark.usefixtures("sessions", "desktop")
def test_resume_one_even_if_listed(
    claude_code: _FakeClaudeCode, tmp_path: pathlib.Path
) -> None:
    _ = get_task_resume(binary_cache_path=tmp_path)(Context(), session_id="11111111")

    assert claude_code.resumed == [_LISTED]


@pytest.mark.usefixtures("sessions", "desktop")
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({}, "not both"),
        ({"session_id": "1", "all_": True}, "not both"),
        ({"session_id": "55555555"}, "does not exist here"),
        ({"session_id": "44444444"}, "no recorded directory"),
    ],
    ids=["neither", "both", "directory not here", "no directory"],
)
def test_resume_that_is_not_possible(
    claude_code: _FakeClaudeCode,
    tmp_path: pathlib.Path,
    kwargs: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        _ = get_task_resume(binary_cache_path=tmp_path)(Context(), **kwargs)

    assert claude_code.resumed == []
