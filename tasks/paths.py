"""Paths used by tasks and tests in this development environment."""

from pathlib import Path

# Secrets directory.
SECRETS_PATH = Path("secrets")

# Path to the AWS profile secrets configuration file.
SECRETS_AWS_PATH = SECRETS_PATH / "aws.toml"

# Path to the Poetry secrets configuration file.
SECRETS_POETRY_PATH = SECRETS_PATH / "poetry.toml"

# Path to the pyfogies tests configuration file.
SECRETS_PYFOGIES_TESTS_PATH = SECRETS_PATH / "pyfogies-tests.toml"

# Template directory.
TEMPLATES_PATH = Path("templates")

# Path to the pyfogies tests configuration template.
TEMPLATE_PYFOGIES_TESTS_PATH = TEMPLATES_PATH / "pyfogies-tests.toml.template"

# Staging directory.
STAGING_PATH = Path(".staging")

# Binary cache directory (inside staging).
STAGING_BINARY_CACHE_PATH = STAGING_PATH / "bin"

# Terraform test backend status file, tracks applied state of the test backend and its states.
TEST_BACKEND_STATUS_PATH = Path("tests/terraform/backend-status.toml")
