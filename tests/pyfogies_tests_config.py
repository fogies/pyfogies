"""Pydantic model and fixture for pyfogies-tests.toml configuration."""

import tomllib
from pathlib import Path

import pytest
from pydantic import BaseModel

from tasks.paths import PATH_SECRETS_PYFOGIES_TESTS


class _AwsConfig(BaseModel):
    profile: str
    region: str


class _DomainConfig(BaseModel):
    zone_name: str


class PyfogiesTestsConfig(BaseModel):
    aws: _AwsConfig
    domain: _DomainConfig | None = None

    @staticmethod
    def load(path: Path) -> "PyfogiesTestsConfig":
        """Load and validate configuration from a TOML file.

        Raises FileNotFoundError if the file does not exist, with a message
        pointing to the template.
        """
        if not path.exists():
            raise FileNotFoundError(
                "pyfogies test configuration file not found: '{}'.\n Copy tests/pyfogies-tests.toml.template to '{}' and fill in the values.".format(
                    path, path
                )
            )
        with path.open("rb") as f:
            data = tomllib.load(f)
        return PyfogiesTestsConfig.model_validate(data)


@pytest.fixture(scope="session")
def pyfogies_test_config() -> PyfogiesTestsConfig:
    """Load and return pyfogies test configuration from pyfogies-tests.toml."""
    return PyfogiesTestsConfig.load(PATH_SECRETS_PYFOGIES_TESTS)
