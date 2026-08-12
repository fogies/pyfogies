"""Paths used by tasks and tests in this development environment."""

from pathlib import Path

# Secrets directory.
PATH_SECRETS = Path("secrets")

# Path to the AWS profile secrets configuration file.
PATH_SECRETS_AWS = PATH_SECRETS / "aws.toml"

# Path to the Poetry secrets configuration file.
PATH_SECRETS_POETRY = PATH_SECRETS / "poetry.toml"

# Path to the pyfogies tests configuration file.
PATH_SECRETS_PYFOGIES_TESTS = PATH_SECRETS / "pyfogies-tests.toml"

# Staging directory.
PATH_STAGING = Path(".staging")

# Binary cache directory (inside staging).
PATH_STAGING_BINARY_CACHE = PATH_STAGING / "bin"
