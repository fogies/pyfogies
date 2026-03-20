"""Test poetry is available."""

import subprocess


def test_poetry_is_available():
    """Test poetry is available by running poetry --version."""
    result = subprocess.run(
        ["poetry", "--version"],
        capture_output=True,
        text=True,
    )

    # Return code 0 indicates success.
    assert result.returncode == 0
