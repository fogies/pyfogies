"""Test isort is available."""

import subprocess


def test_isort_is_available():
    """Test isort is available by running isort --version."""
    result = subprocess.run(
        ["isort", "--version"],
        capture_output=True,
        text=True,
    )

    # Return code 0 indicates success.
    assert result.returncode == 0
