"""Test black is available."""

import subprocess


def test_black_is_available():
    """Test black is available by running black --version."""
    result = subprocess.run(
        ["black", "--version"],
        capture_output=True,
        text=True,
    )

    # Return code 0 indicates success.
    assert result.returncode == 0
