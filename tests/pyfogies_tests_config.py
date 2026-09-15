"""Pydantic model and fixture for pyfogies-tests.toml configuration."""

import tomllib
from pathlib import Path

import pytest
from pydantic import BaseModel

from fogies.templates import ensure_from_template
from tasks.paths import PATH_SECRETS_PYFOGIES_TESTS, PATH_TEMPLATE_PYFOGIES_TESTS


def _pyfogies_tests_toml_template_factory() -> str:
    return PATH_TEMPLATE_PYFOGIES_TESTS.read_text(encoding="utf-8")


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
        ensure_from_template(
            path=path, template_factory=_pyfogies_tests_toml_template_factory
        )
        with path.open("rb") as f:
            data = tomllib.load(f)
        return PyfogiesTestsConfig.model_validate(data)


@pytest.fixture(scope="session")
def pyfogies_test_config() -> PyfogiesTestsConfig:
    """Load and return pyfogies test configuration from pyfogies-tests.toml."""
    return PyfogiesTestsConfig.load(path=PATH_SECRETS_PYFOGIES_TESTS)
