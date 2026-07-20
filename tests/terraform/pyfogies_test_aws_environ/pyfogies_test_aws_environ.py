"""Fixture for AWS environment configuration."""

from collections.abc import Iterator

import pytest
from fogies_paths import AWS_PROFILE_PYFOGIES_TEST, PATH_SECRETS_AWS

from fogies.tools.aws_environ import AwsEnviron, aws_environ


@pytest.fixture(scope="session")
def pyfogies_test_aws_environ() -> Iterator[AwsEnviron]:
    """Set AWS credentials from the pyfogies test profile; yield the active environment."""
    with aws_environ(
        profiles_path=PATH_SECRETS_AWS,
        profile=AWS_PROFILE_PYFOGIES_TEST,
    ) as aws_env:
        yield aws_env
