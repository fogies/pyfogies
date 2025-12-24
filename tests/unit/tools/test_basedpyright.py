"""Test basedpyright is available."""

import subprocess


def test_basedpyright_is_available():
    """Test basedpyright is available by running basedpyright --version."""
    result = subprocess.run(
        ["basedpyright", "--version"],
        capture_output=True,
        text=True,
    )

    # Return code 0 indicates success.
    assert result.returncode == 0
