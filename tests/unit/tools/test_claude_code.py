"""Test Claude Code is available, and what is run with it."""

import pathlib
import subprocess

import pytest

from fogies.tools.claude_code import claude_code
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
