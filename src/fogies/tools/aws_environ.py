"""Helpers for configuring AWS-related environment variables."""

from __future__ import annotations

import contextlib
import tomllib
from collections.abc import Generator
from pathlib import Path
from typing import cast

import botocore.exceptions
from pydantic import BaseModel

from fogies.templates import aws_toml_template_factory, ensure_from_template
from fogies.tools.environ import environ
from fogies.typing import boto_client_sts


class AwsProfile(BaseModel):
    """AWS credentials for a named profile, as stored in a TOML profiles file."""

    name: str
    aws_access_key_id: str
    aws_secret_access_key: str


class AwsEnviron(BaseModel):
    profile: str
    aws_access_key_id: str


# Type for passing a pre-built AWS environment context manager (e.g. from
# aws_environ_from_toml() or aws_environ_from_profile()) into a task factory,
# to be entered when (and only when) the task actually runs.
AwsEnvironContextManager = contextlib.AbstractContextManager[AwsEnviron]


def load_aws_profile_from_toml(profiles_path: Path, profile_name: str) -> AwsProfile:
    """Return AWS profile loaded from a TOML profiles file.

    The file is expected to contain a table for each profile, for example:

    [test]
    aws_access_key_id = "value-id"
    aws_secret_access_key = "value-secret"

    Created from a template if it doesn't exist yet.
    """
    if profiles_path.suffix != ".toml":
        raise ValueError(
            "AWS profiles file must have .toml extension, got '{}'".format(
                profiles_path
            )
        )
    ensure_from_template(path=profiles_path, template_factory=aws_toml_template_factory)

    with profiles_path.open("rb") as profiles_file:
        data: dict[str, object] = tomllib.load(profiles_file)

    try:
        profile_raw = data[profile_name]
    except KeyError as exc:
        raise KeyError(
            "AWS profile '{}' not found in '{}'".format(
                profile_name,
                profiles_path,
            )
        ) from exc

    profile_data = cast(dict[str, object], profile_raw)
    return AwsProfile.model_validate({"name": profile_name, **profile_data})


@contextlib.contextmanager
def aws_environ_from_profile(
    *,
    profile: AwsProfile,
    raise_if_exists: bool = True,
    raise_if_changed: bool = True,
) -> Generator[AwsEnviron]:
    """Context manager that applies AWS variables from an already-known profile.

    For credentials obtained some other way (e.g. prompted interactively, or
    freshly created/rotated) rather than read from a TOML profiles file; see
    aws_environ_from_toml() for that case, which delegates here.

    Confirms the credentials actually work (via STS GetCallerIdentity) before
    yielding, raising ValueError immediately rather than letting some later,
    unrelated AWS call fail confusingly. The extra round trip is minor next
    to the time lost misdiagnosing an unclear downstream error.

    Yields an :class:`AwsEnviron` describing which profile and key ID are active.
    """
    variables: dict[str, str] = {
        "AWS_ACCESS_KEY_ID": profile.aws_access_key_id,
        "AWS_SECRET_ACCESS_KEY": profile.aws_secret_access_key,
    }
    with environ(
        variables=variables,
        raise_if_exists=raise_if_exists,
        raise_if_changed=raise_if_changed,
    ):
        try:
            _ = boto_client_sts().get_caller_identity()
        except botocore.exceptions.ClientError as exc:
            raise ValueError(
                "Invalid AWS credentials for profile '{}': {}".format(profile.name, exc)
            ) from exc
        yield AwsEnviron(
            profile=profile.name,
            aws_access_key_id=profile.aws_access_key_id,
        )


@contextlib.contextmanager
def aws_environ_from_toml(
    *,
    profiles_path: Path,
    profile_name: str,
    raise_if_exists: bool = True,
    raise_if_changed: bool = True,
) -> Generator[AwsEnviron]:
    """Context manager that applies AWS variables read from a TOML file.

    The *profiles_path* parameter specifies the AWS TOML profiles file to read;
    it must have a ``.toml`` extension. The *profile_name* parameter specifies
    the AWS profile name, which is mapped to a ``[<name>]`` table in the
    profiles file. See aws_environ_from_profile() for credential validation.

    Yields an :class:`AwsEnviron` describing which profile and key ID are active.
    """
    aws_profile = load_aws_profile_from_toml(
        profiles_path=profiles_path, profile_name=profile_name
    )
    with aws_environ_from_profile(
        profile=aws_profile,
        raise_if_exists=raise_if_exists,
        raise_if_changed=raise_if_changed,
    ) as env:
        yield env
