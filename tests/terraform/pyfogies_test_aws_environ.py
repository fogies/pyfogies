"""Fixture for AWS environment configuration."""

from collections.abc import Iterator

import pytest

from fogies.tools.aws_environ import AwsEnviron, aws_environ_from_config
from tasks.paths import PATH_SECRETS_AWS
from tests.pyfogies_tests_config import PyfogiesTestsConfig


@pytest.fixture(scope="session")
def pyfogies_test_aws_environ(
    pyfogies_test_config: PyfogiesTestsConfig,
) -> Iterator[AwsEnviron]:
    """Set AWS credentials from the configured profile; yield the active environment."""
    with aws_environ_from_config(
        config_path=PATH_SECRETS_AWS,
        profile_name=pyfogies_test_config.aws.profile,
        raise_if_env_exists=False,
    ) as aws_env:
        yield aws_env
