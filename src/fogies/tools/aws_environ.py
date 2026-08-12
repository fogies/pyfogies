"""Helpers for configuring AWS-related environment variables."""

from __future__ import annotations

import contextlib
import tomllib
from collections.abc import Generator
from pathlib import Path

from pydantic import BaseModel

from fogies.tools.environ import environ


class AwsEnviron(BaseModel):
    profile: str
    aws_access_key_id: str


# Type for passing a pre-built aws_environ() context manager into a task
# factory, to be entered when (and only when) the task actually runs.
AwsEnvironContextManager = contextlib.AbstractContextManager[AwsEnviron]


class _AwsProfile(BaseModel):
    aws_access_key_id: str
    aws_secret_access_key: str


def _load_aws_profile_from_toml(profiles_path: Path, profile: str) -> _AwsProfile:
    """Return AWS profile loaded from a TOML profiles file.

    The file is expected to contain a table for each profile, for example:

    [test]
    aws_access_key_id = "value-id"
    aws_secret_access_key = "value-secret"
    """
    if profiles_path.suffix != ".toml":
        raise ValueError(
            "AWS profiles file must have .toml extension, got '{}'".format(
                profiles_path
            )
        )
    if not profiles_path.exists():
        raise FileNotFoundError(
            "AWS profiles file '{}' does not exist.\nSee provided template.".format(
                profiles_path
            )
        )

    with profiles_path.open("rb") as profiles_file:
        data: dict[str, object] = tomllib.load(profiles_file)

    try:
        profile_raw = data[profile]
    except KeyError as exc:
        raise KeyError(
            "AWS profile '{}' not found in '{}'".format(
                profile,
                profiles_path,
            )
        ) from exc

    return _AwsProfile.model_validate(profile_raw)


@contextlib.contextmanager
def aws_environ(
    *,
    profiles_path: Path,
    profile: str,
    raise_if_exists: bool = True,
    raise_if_changed: bool = True,
) -> Generator[AwsEnviron]:
    """Context manager that applies AWS variables from a TOML file.

    The *profiles_path* parameter specifies the AWS TOML profiles file to read;
    it must have a ``.toml`` extension. The *profile* parameter specifies the
    AWS profile name, which is mapped to a ``[<name>]`` table in the profiles
    file.

    Yields an :class:`AwsEnviron` describing which profile and key ID are active.
    """
    aws_profile = _load_aws_profile_from_toml(
        profiles_path=profiles_path, profile=profile
    )
    variables: dict[str, str] = {
        "AWS_ACCESS_KEY_ID": aws_profile.aws_access_key_id,
        "AWS_SECRET_ACCESS_KEY": aws_profile.aws_secret_access_key,
    }
    with environ(
        variables=variables,
        raise_if_exists=raise_if_exists,
        raise_if_changed=raise_if_changed,
    ):
        yield AwsEnviron(
            profile=profile,
            aws_access_key_id=aws_profile.aws_access_key_id,
        )
