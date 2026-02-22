"""Test Terraform context manager downloads and runs correctly."""

import pathlib
import subprocess

from fogies.tools.terraform import terraform
from paths import PATH_STAGING_BINARY_CACHE


def test_terraform_is_available():
    """Test that context manager provides a working executable."""
    with terraform(path_binary_cache=PATH_STAGING_BINARY_CACHE) as tf:
        # Verify the executable exists.
        assert tf.path.exists()

        # Run the executable and verify the version matches.
        result = subprocess.run(
            [str(tf.path), "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert tf.version in result.stdout
