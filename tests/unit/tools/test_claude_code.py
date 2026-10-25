"""Test Claude Code is available, and what is run with it."""

import pathlib
import subprocess

import pytest
from claude_agent_sdk import SDKSessionInfo

from fogies.tools.claude_code import (
    claude_code,
    describe_session,
    find_session_id,
)
from tasks.paths import STAGING_BINARY_CACHE_PATH


def test_claude_code_is_available() -> None:
    """Context manager provides a working executable."""
    with claude_code(binary_cache_path=STAGING_BINARY_CACHE_PATH) as cc:
        # Verify the executable exists.
        assert cc.binary_path.exists()

        # Run the executable and verify the version matches.
        result = subprocess.run(
            [str(cc.binary_path), "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert cc.binary_version in result.stdout


def test_claude_code_unknown_version() -> None:
    """An unknown version is refused before anything is downloaded."""
    with pytest.raises(ValueError, match="Unknown Claude Code version"):
        with claude_code(version="0.0.0", binary_cache_path=STAGING_BINARY_CACHE_PATH):
            pass


def test_resume_in_desktop_requires_directory(tmp_path: pathlib.Path) -> None:
    """A session is not resumed unless its directory exists here."""
    with claude_code(binary_cache_path=STAGING_BINARY_CACHE_PATH) as cc:
        with pytest.raises(ValueError, match="does not exist here"):
            cc.resume_in_desktop(session_id="abc", cwd=tmp_path / "missing")


def test_auth_status_not_signed_in(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not being signed in is the answer, not an error."""
    # A config directory of its own, and nothing else to sign in with.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)

    with claude_code(binary_cache_path=STAGING_BINARY_CACHE_PATH) as cc:
        assert cc.auth_status() is False


_IDS = [
    "60c0de8b-271f-4239-830d-bbe9838a631c",
    "60d1aa00-0000-4000-8000-000000000000",
    "f542028f-01b1-4734-ad54-e30e6b957005",
]


def test_find_session_id_from_part_of_it() -> None:
    """Any part of an ID, from any case, that is in only one, including all of it."""
    # The start, as with git.
    assert find_session_id(_IDS, "f54") == _IDS[2]
    assert find_session_id(_IDS, "F542028F") == _IDS[2]
    # From inside it.
    assert find_session_id(_IDS, "01b1") == _IDS[2]
    # All of it.
    assert find_session_id(_IDS, _IDS[2]) == _IDS[2]


@pytest.mark.parametrize(
    ("value", "match"),
    [
        ("60", "matches 2 sessions"),
        ("-", "matches 3 sessions"),
        ("zzzz", "No session"),
        ("  ", "at least part"),
    ],
    ids=["ambiguous start", "ambiguous inside", "none", "empty"],
)
def test_find_session_id_that_is_not_one(value: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _ = find_session_id(_IDS, value)


def test_describe_session() -> None:
    """A session is described by its ID, where it ran, and a title that is kept short."""
    session = SDKSessionInfo(
        session_id=_IDS[0],
        summary="Fix\nthe   thing " + "x" * 100,
        last_modified=1_700_000_000_000,
        cwd="/work/demo",
    )
    line = describe_session(session)
    assert line.startswith(_IDS[0])
    assert "demo" in line
    assert line.endswith("...")
    assert "\n" not in line
