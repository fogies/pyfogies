"""Test the tasks for Claude Code sessions."""

import json
import pathlib
from collections.abc import Callable

import pytest
from invoke.context import Context

from fogies.tasks.claude_code import get_collection, get_task_delete

_SESSION_ID = "60c0de8b-271f-4239-830d-bbe9838a631c"


def _answering(answer: str) -> Callable[[str], str]:
    """Return what replaces input(), giving answer to any prompt."""
    return lambda prompt: answer


@pytest.fixture
def session_file(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> pathlib.Path:
    """A session, with subagent transcripts, in a Claude config directory of its own."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    project = tmp_path / "projects" / "demo"
    project.mkdir(parents=True)
    entry = {
        "type": "user",
        "uuid": "11111111-1111-4111-8111-111111111111",
        "sessionId": _SESSION_ID,
        "cwd": str(tmp_path),
        "message": {"role": "user", "content": "Hello"},
    }
    session = project / (_SESSION_ID + ".jsonl")
    _ = session.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    subagents = project / _SESSION_ID / "subagents"
    subagents.mkdir(parents=True)
    _ = (subagents / "agent.jsonl").write_text("{}\n", encoding="utf-8")
    return session


def test_delete_deletes_after_confirming(
    session_file: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A session is found from part of its ID and deleted, with what it holds."""
    monkeypatch.setattr("builtins.input", _answering("y"))

    _ = get_task_delete()(Context(), session_id="60c0de")

    assert not session_file.exists()
    assert not (session_file.parent / _SESSION_ID).exists()


@pytest.mark.parametrize("answer", ["", "n", "no"])
def test_delete_keeps_the_session_unless_confirmed(
    session_file: pathlib.Path, monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    monkeypatch.setattr("builtins.input", _answering(answer))

    _ = get_task_delete()(Context(), session_id=_SESSION_ID)

    assert session_file.exists()


def test_delete_a_session_that_is_not_here(session_file: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="No session"):
        _ = get_task_delete()(Context(), session_id="ffffffff")

    assert session_file.exists()


@pytest.mark.parametrize(
    ("kwargs", "has_delete"),
    [({}, False), ({"include_delete": False}, False), ({"include_delete": True}, True)],
    ids=["by default", "excluded", "included"],
)
def test_collection_includes_delete_only_when_asked(
    tmp_path: pathlib.Path, kwargs: dict[str, bool], has_delete: bool
) -> None:
    collection = get_collection(
        collection_name="claude-code", binary_cache_path=tmp_path, **kwargs
    )

    assert ("delete" in collection.tasks) is has_delete
