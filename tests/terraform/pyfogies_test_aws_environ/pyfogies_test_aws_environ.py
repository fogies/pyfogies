"""Fixture for AWS environment configuration."""

from collections.abc import Iterator

import pytest
from fogies_paths import PATH_SECRETS_AWS

from tests.pyfogies_tests_config import PyfogiesTestsConfig
from fogies.tools.aws_environ import AwsEnviron, aws_environ


@pytest.fixture(scope="session")
def pyfogies_test_aws_environ(
    pyfogies_test_config: PyfogiesTestsConfig,
) -> Iterator[AwsEnviron]:
    """Set AWS credentials from the configured profile; yield the active environment."""
    with aws_environ(
        profiles_path=PATH_SECRETS_AWS,
        profile=pyfogies_test_config.aws.profile,
    ) as aws_env:
        yield aws_env
