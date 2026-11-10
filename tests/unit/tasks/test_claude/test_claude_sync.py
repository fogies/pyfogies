"""Test the tasks for claude-sync."""

import contextlib
import pathlib
from collections.abc import Callable, Generator

import pytest
from invoke.context import Context

from fogies.tasks.claude_sync import get_task_delete
from fogies.tools.claude_sync import ClaudeSyncConfig

from .conftest import WriteSession

_SESSION_ID = "60c0de8b-271f-4239-830d-bbe9838a631c"

_CONFIG = ClaudeSyncConfig(
    aws_profile="profile", bucket="bucket", region="us-west-2", scope="sessions"
)


def _answering(answer: str) -> Callable[[str], str]:
    """Return what replaces input(), giving answer to any prompt."""
    return lambda prompt: answer


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, str]]]:
    """Replace what reaches the bucket and deletes, and record what is called."""
    calls: list[tuple[str, dict[str, str]]] = []

    @contextlib.contextmanager
    def fake_aws_environ(**kwargs: object) -> Generator[None]:
        assert kwargs["profile_name"] == "profile"
        yield

    def fake_record_deletion(**kwargs: str) -> None:
        calls.append(("record_deletion", kwargs))

    def fake_apply_deletion_locally(session_id: str) -> bool:
        calls.append(("apply_deletion_locally", {"session_id": session_id}))
        return True

    def fake_load_claude_sync_config(**kwargs: object) -> ClaudeSyncConfig:
        _ = kwargs
        return _CONFIG

    monkeypatch.setattr(
        "fogies.tasks.claude_sync.load_claude_sync_config",
        fake_load_claude_sync_config,
    )
    monkeypatch.setattr(
        "fogies.tasks.claude_sync.aws_environ_from_config", fake_aws_environ
    )
    monkeypatch.setattr(
        "fogies.tasks.claude_sync.record_deletion", fake_record_deletion
    )
    monkeypatch.setattr(
        "fogies.tasks.claude_sync.apply_deletion_locally", fake_apply_deletion_locally
    )
    return calls


def _delete(session_id: str) -> None:
    _ = get_task_delete(
        claude_sync_config_path=pathlib.Path("claude-sync.toml"),
        aws_config_path=pathlib.Path("aws.toml"),
    )(Context(), session_id=session_id)


def test_delete_records_it_then_deletes_it_here_after_confirming(
    write_session: WriteSession,
    tmp_path: pathlib.Path,
    calls: list[tuple[str, dict[str, str]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A session is found from part of its ID, and the bucket is the config's."""
    _ = write_session(_SESSION_ID, tmp_path)
    monkeypatch.setattr("builtins.input", _answering("y"))

    _delete("60c0de")

    assert calls == [
        (
            "record_deletion",
            {"bucket_name": "bucket", "region": "us-west-2", "session_id": _SESSION_ID},
        ),
        ("apply_deletion_locally", {"session_id": _SESSION_ID}),
    ]


def test_delete_deletes_nothing_unless_confirmed(
    write_session: WriteSession,
    tmp_path: pathlib.Path,
    calls: list[tuple[str, dict[str, str]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = write_session(_SESSION_ID, tmp_path)
    monkeypatch.setattr("builtins.input", _answering(""))

    _delete(_SESSION_ID)

    assert calls == []


@pytest.mark.usefixtures("write_session")
def test_delete_a_session_that_is_not_here(
    calls: list[tuple[str, dict[str, str]]],
) -> None:
    with pytest.raises(ValueError, match="No session"):
        _delete("ffffffff")

    assert calls == []


def test_delete_deletes_nothing_here_if_it_cannot_record(
    write_session: WriteSession,
    tmp_path: pathlib.Path,
    calls: list[tuple[str, dict[str, str]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = write_session(_SESSION_ID, tmp_path)
    monkeypatch.setattr("builtins.input", _answering("y"))

    def failing_record_deletion(**kwargs: str) -> None:
        _ = kwargs
        raise RuntimeError("kept changing")

    monkeypatch.setattr(
        "fogies.tasks.claude_sync.record_deletion", failing_record_deletion
    )

    with pytest.raises(RuntimeError, match="kept changing"):
        _delete(_SESSION_ID)

    assert calls == []
