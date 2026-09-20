"""Test Terraform is available."""

import subprocess

from fogies.tools.terraform import terraform
from tasks.paths import STAGING_BINARY_CACHE_PATH


def test_terraform_is_available() -> None:
    """Context manager provides a working executable."""
    with terraform(binary_cache_path=STAGING_BINARY_CACHE_PATH) as tf:
        # Verify the executable exists.
        assert tf.binary_path.exists()

        # Run the executable and verify the version matches.
        result = subprocess.run(
            [str(tf.binary_path), "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert tf.binary_version in result.stdout
