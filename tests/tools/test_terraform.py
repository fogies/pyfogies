"""Test Terraform is available."""

import subprocess

from fogies.tools.terraform import terraform
from tasks.paths import PATH_STAGING_BINARY_CACHE


def test_terraform_is_available() -> None:
    """Context manager provides a working executable."""
    with terraform(binary_cache_path=PATH_STAGING_BINARY_CACHE) as tf:
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
