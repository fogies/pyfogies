"""Test claude-sync is available."""

import subprocess

from fogies.tools.claude_sync import claude_sync
from tasks.paths import PATH_STAGING_BINARY_CACHE


def test_claude_sync_is_available() -> None:
    """Context manager provides a working executable exposing the wrapped commands.

    Only checks --help, not push/pull/status themselves: those read
    ~/.claude-sync/config.yaml with no override, so any test exercising them
    would depend on this machine's ambient claude-sync setup rather than a
    controlled fixture.
    """
    with claude_sync(
        binary_cache_path=PATH_STAGING_BINARY_CACHE, raise_if_env_exists=False
    ) as cs:
        # Verify the executable exists.
        assert cs.binary_path.exists()

        # Run the executable and verify it exposes the commands this tool wraps.
        result = subprocess.run(
            [str(cs.binary_path), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "push" in result.stdout
        assert "pull" in result.stdout
        assert "status" in result.stdout
