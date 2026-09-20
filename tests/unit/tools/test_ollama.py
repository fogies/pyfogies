"""Test Ollama CLI is available."""

import subprocess

from fogies.tools.ollama import ollama
from tasks.paths import STAGING_BINARY_CACHE_PATH


def test_ollama_is_available() -> None:
    """Context manager provides a working executable."""
    with ollama(binary_cache_path=STAGING_BINARY_CACHE_PATH) as ol:
        # Verify the executable exists.
        assert ol.binary_path.exists()

        # Run the executable and verify the version matches.
        result = subprocess.run(
            [str(ol.binary_path), "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert ol.binary_version in result.stdout
