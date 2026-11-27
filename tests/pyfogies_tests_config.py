"""Pydantic model and fixture for pyfogies-tests.toml configuration."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from fogies.config import load_config
from tasks.paths import SECRETS_PYFOGIES_TESTS_PATH, TEMPLATE_PYFOGIES_TESTS_PATH


def _pyfogies_tests_toml_template_factory() -> str:
    return TEMPLATE_PYFOGIES_TESTS_PATH.read_text(encoding="utf-8")


class _AwsConfig(BaseModel):
    profile: str
    region: str


class _DomainConfig(BaseModel):
    zone_name: str


class PyfogiesTestsConfig(BaseModel):
    aws: _AwsConfig
    domain: _DomainConfig | None = None

    @staticmethod
    def load(*, path: Path) -> "PyfogiesTestsConfig":
        """Load and validate configuration from a TOML file.

        Created from a template if it doesn't exist yet -- callers should
        expect a FileNotFoundError-style failure the first time, prompting
        them to fill in the newly-created file and re-run.
        """
        return load_config(
            path=path,
            model=PyfogiesTestsConfig,
            template_factory=_pyfogies_tests_toml_template_factory,
        )


@pytest.fixture(scope="session")
def pyfogies_test_config() -> PyfogiesTestsConfig:
    """Load and return pyfogies tests configuration from pyfogies-tests.toml."""
    return PyfogiesTestsConfig.load(path=SECRETS_PYFOGIES_TESTS_PATH)
