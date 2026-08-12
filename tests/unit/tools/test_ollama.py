"""Test Ollama CLI is available."""

import subprocess

from fogies.tools.ollama import ollama
from tasks.paths import PATH_STAGING_BINARY_CACHE


def test_ollama_is_available() -> None:
    """Context manager provides a working executable."""
    with ollama(binary_cache_path=PATH_STAGING_BINARY_CACHE) as ol:
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
