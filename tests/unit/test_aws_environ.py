"""Tests for fogies.tools.aws_environ."""

import os
from pathlib import Path

import pytest

from fogies.tools.aws_environ import aws_environ


def test_aws_environ_sets_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """aws_environ loads variables from a TOML profiles file using environ."""

    # Start from a clean environment for these variables within this test.
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    profiles_path = tmp_path / "test_aws_environ.toml"
    config_text = "\n".join(
        [
            "[test]",
            'aws_access_key_id = "value-aws-access-key-id"',
            'aws_secret_access_key = "value-aws-secret-access-key"',
            "",
            "[test-other]",
            'aws_access_key_id = "other-value-aws-access-key-id"',
            'aws_secret_access_key = "other-value-aws-secret-access-key"',
            "",
        ]
    )
    _ = profiles_path.write_text(config_text, encoding="utf-8")

    with aws_environ(profiles_path=profiles_path, profile="test"):
        assert os.environ.get("AWS_ACCESS_KEY_ID") == "value-aws-access-key-id"
        assert os.environ.get("AWS_SECRET_ACCESS_KEY") == "value-aws-secret-access-key"

    with aws_environ(profiles_path=profiles_path, profile="test-other"):
        assert os.environ.get("AWS_ACCESS_KEY_ID") == "other-value-aws-access-key-id"
        assert (
            os.environ.get("AWS_SECRET_ACCESS_KEY")
            == "other-value-aws-secret-access-key"
        )

    assert "AWS_ACCESS_KEY_ID" not in os.environ
    assert "AWS_SECRET_ACCESS_KEY" not in os.environ


def test_aws_environ_raises_for_missing_file(tmp_path: Path) -> None:
    """aws_environ raises FileNotFoundError when profiles file does not exist."""
    profiles_path = tmp_path / "missing.toml"

    with pytest.raises(FileNotFoundError):
        _ = aws_environ(profiles_path=profiles_path, profile="test")


def test_aws_environ_raises_for_toml_extension(tmp_path: Path) -> None:
    """aws_environ raises ValueError when profiles path does not have .toml extension."""
    profiles_path = tmp_path / "aws.env"

    with pytest.raises(ValueError, match=r"must have \.toml extension"):
        _ = aws_environ(profiles_path=profiles_path, profile="test")
