"""Fixtures shared by the tests of the Claude tasks."""

import json
import pathlib
from collections.abc import Callable

import pytest

# Writes a session with the given ID, that ran in the given directory (if any),
# and returns its transcript.
WriteSession = Callable[[str, pathlib.Path | None], pathlib.Path]


@pytest.fixture
def write_session(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> WriteSession:
    """Write sessions into a Claude config directory of its own."""
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    project = tmp_path / "claude" / "projects" / "demo"
    project.mkdir(parents=True)

    def write(session_id: str, cwd: pathlib.Path | None) -> pathlib.Path:
        entry: dict[str, object] = {
            "type": "user",
            "uuid": "11111111-1111-4111-8111-111111111111",
            "sessionId": session_id,
            "message": {"role": "user", "content": "Hello"},
        }
        if cwd is not None:
            entry["cwd"] = str(cwd)
        session = project / (session_id + ".jsonl")
        _ = session.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        return session

    return write
