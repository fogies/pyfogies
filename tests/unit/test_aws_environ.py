"""Tests for fogies.tools.aws_environ.

Credential validation makes a real STS call, so these tests use real
credentials from the local secrets file (like tests/unit/test_aws_access_key.py,
no mocks) rather than faking STS or using placeholder values that could never
validate.
"""

import os
from pathlib import Path

import pytest

from fogies.tools.aws_environ import (
    _username_from_iam_arn,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.aws_environ import (
    AwsProfile,
    aws_environ_from_config,
    aws_environ_from_profile,
    load_aws_profile_from_config,
)
from tasks.paths import PATH_SECRETS_AWS
from tests.pyfogies_tests_config import PyfogiesTestsConfig


def test_aws_environ_from_profile_sets_variables(
    monkeypatch: pytest.MonkeyPatch, pyfogies_test_config: PyfogiesTestsConfig
) -> None:
    """aws_environ_from_profile sets variables from an AwsProfile using environ."""
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    profile = load_aws_profile_from_config(
        config_path=PATH_SECRETS_AWS, profile_name=pyfogies_test_config.aws.profile
    )

    with aws_environ_from_profile(profile=profile) as env:
        assert env.profile == profile.name
        assert env.aws_access_key_id == profile.aws_access_key_id
        assert os.environ.get("AWS_ACCESS_KEY_ID") == profile.aws_access_key_id
        assert os.environ.get("AWS_SECRET_ACCESS_KEY") == profile.aws_secret_access_key

    assert "AWS_ACCESS_KEY_ID" not in os.environ
    assert "AWS_SECRET_ACCESS_KEY" not in os.environ


def test_aws_environ_from_profile_raises_for_invalid_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """aws_environ_from_profile raises ValueError when credentials don't validate.

    Also confirms env vars are still restored on the way out, even though
    validation fails before the context manager ever yields.
    """
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    invalid_profile = AwsProfile(
        name="invalid",
        aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
        aws_secret_access_key="not-a-real-secret-key",
    )

    with pytest.raises(ValueError, match="Invalid AWS credentials"):
        with aws_environ_from_profile(profile=invalid_profile):
            pass

    assert "AWS_ACCESS_KEY_ID" not in os.environ
    assert "AWS_SECRET_ACCESS_KEY" not in os.environ


def test_aws_environ_from_config_reads_selected_profile(
    monkeypatch: pytest.MonkeyPatch,
    pyfogies_test_config: PyfogiesTestsConfig,
    tmp_path: Path,
) -> None:
    """aws_environ_from_config loads the named profile's credentials from the file.

    Env-var set/restore mechanics are covered by
    test_aws_environ_from_profile_sets_variables; aws_environ_from_config
    delegates to aws_environ_from_profile for that. This test only covers
    what's specific to aws_environ_from_config: reading the right profile out
    of a multi-profile file. The unselected "decoy" profile's credentials are
    never validated, so they don't need to be real.
    """
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    profile = load_aws_profile_from_config(
        config_path=PATH_SECRETS_AWS, profile_name=pyfogies_test_config.aws.profile
    )

    config_path = tmp_path / "test_aws_environ.toml"
    config_text = "\n".join(
        [
            "[decoy]",
            'aws_access_key_id = "not-a-real-key"',
            'aws_secret_access_key = "not-a-real-secret"',
            "",
            "[selected]",
            'aws_access_key_id = "{}"'.format(profile.aws_access_key_id),
            'aws_secret_access_key = "{}"'.format(profile.aws_secret_access_key),
            "",
        ]
    )
    _ = config_path.write_text(config_text, encoding="utf-8")

    with aws_environ_from_config(
        config_path=config_path, profile_name="selected"
    ) as env:
        assert env.profile == "selected"
        assert env.aws_access_key_id == profile.aws_access_key_id
        assert os.environ.get("AWS_ACCESS_KEY_ID") == profile.aws_access_key_id

    assert "AWS_ACCESS_KEY_ID" not in os.environ


def test_load_aws_profile_from_config_raises_for_missing_profile(
    tmp_path: Path,
) -> None:
    """load_aws_profile_from_config raises KeyError when the profile isn't in the file."""
    config_path = tmp_path / "config.toml"
    config_text = "\n".join(
        [
            "[other]",
            'aws_access_key_id = "not-a-real-key"',
            'aws_secret_access_key = "not-a-real-secret"',
            "",
        ]
    )
    _ = config_path.write_text(config_text, encoding="utf-8")

    with pytest.raises(KeyError, match="not found"):
        _ = load_aws_profile_from_config(config_path=config_path, profile_name="test")


def test_load_aws_profile_from_config_raises_for_missing_file(
    tmp_path: Path,
) -> None:
    """load_aws_profile_from_config creates a template and raises, rather than reading it."""
    config_path = tmp_path / "config.toml"
    assert not config_path.exists()

    with pytest.raises(FileNotFoundError, match="was not found"):
        _ = load_aws_profile_from_config(config_path=config_path, profile_name="test")

    assert config_path.exists()


@pytest.mark.parametrize(
    ("arn", "expected_username"),
    [
        ("arn:aws:iam::123456789012:user/alice", "alice"),
        ("arn:aws:iam::123456789012:user/team/alice", "alice"),
        ("arn:aws:sts::123456789012:assumed-role/SomeRole/session-name", None),
        ("not-an-arn", None),
    ],
)
def test_username_from_iam_arn(arn: str, expected_username: str | None) -> None:
    """Returns the username for an IAM user ARN; raises for any other shape."""
    if expected_username is None:
        with pytest.raises(ValueError, match="Expected an IAM user ARN"):
            _ = _username_from_iam_arn(arn)
    else:
        assert _username_from_iam_arn(arn) == expected_username
