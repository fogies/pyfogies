"""Test the tasks for Claude Code sessions."""

import pathlib
from collections.abc import Callable

import pytest
from invoke.context import Context

from fogies.tasks.claude_code import get_task_delete

from .conftest import WriteSession

_SESSION_ID = "60c0de8b-271f-4239-830d-bbe9838a631c"


def _answering(answer: str) -> Callable[[str], str]:
    """Return what replaces input(), giving answer to any prompt."""
    return lambda prompt: answer


def test_delete_deletes_after_confirming(
    write_session: WriteSession, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A session is found from part of its ID and deleted, with what it holds."""
    monkeypatch.setattr("builtins.input", _answering("y"))
    session = write_session(_SESSION_ID, tmp_path)
    subagents = session.parent / _SESSION_ID / "subagents"
    subagents.mkdir(parents=True)
    _ = (subagents / "agent.jsonl").write_text("{}\n", encoding="utf-8")

    _ = get_task_delete()(Context(), session_id="60c0de")

    assert not session.exists()
    assert not (session.parent / _SESSION_ID).exists()


@pytest.mark.parametrize("answer", ["", "n"])
def test_delete_keeps_the_session_unless_confirmed(
    write_session: WriteSession,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    answer: str,
) -> None:
    monkeypatch.setattr("builtins.input", _answering(answer))
    session = write_session(_SESSION_ID, tmp_path)

    _ = get_task_delete()(Context(), session_id=_SESSION_ID)

    assert session.exists()


def test_delete_a_session_that_is_not_here(
    write_session: WriteSession, tmp_path: pathlib.Path
) -> None:
    session = write_session(_SESSION_ID, tmp_path)

    with pytest.raises(ValueError, match="No session"):
        _ = get_task_delete()(Context(), session_id="ffffffff")

    assert session.exists()
