"""IAM user and access key management, independent of invoke."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from fogies.tools.aws_environ import AwsProfile
from fogies.typing import boto_client_iam

if TYPE_CHECKING:
    from mypy_boto3_iam.type_defs import AccessKeyMetadataTypeDef


class _IamAccessKeyInfo(BaseModel):
    key_id: str
    status: str
    created: datetime.datetime | None
    last_used: datetime.datetime | None


class IamAccessKeys(BaseModel):
    current: _IamAccessKeyInfo | None  # newest key
    previous: _IamAccessKeyInfo | None  # oldest key; only present when two keys exist


class _IamUserInfo(BaseModel):
    username: str
    keys: IamAccessKeys


def get_keys(*, username: str) -> IamAccessKeys:
    """Return the access keys for an IAM user as current (newest) and previous (oldest).

    Raises ValueError if the IAM user does not exist.
    """
    iam = boto_client_iam()
    try:
        raw_keys = iam.list_access_keys(UserName=username)["AccessKeyMetadata"]
    except iam.exceptions.NoSuchEntityException as exc:
        raise ValueError("IAM user '{}' not found.".format(username)) from exc
    sorted_keys = sorted(
        raw_keys,
        key=lambda k: k.get("CreateDate") or datetime.datetime.min,
        reverse=True,
    )

    def _to_info(raw_key: AccessKeyMetadataTypeDef) -> _IamAccessKeyInfo:
        key_id = raw_key.get("AccessKeyId", "")
        last_used_response = iam.get_access_key_last_used(AccessKeyId=key_id)
        last_used = last_used_response["AccessKeyLastUsed"].get("LastUsedDate")
        return _IamAccessKeyInfo(
            key_id=key_id,
            status=raw_key.get("Status", ""),
            created=raw_key.get("CreateDate"),
            last_used=last_used,
        )

    return IamAccessKeys(
        current=_to_info(sorted_keys[0]) if len(sorted_keys) >= 1 else None,
        previous=_to_info(sorted_keys[1]) if len(sorted_keys) >= 2 else None,
    )


def list_users() -> list[_IamUserInfo]:
    """List all IAM users (sorted by name) and their access keys."""
    iam = boto_client_iam()
    raw_users = [
        user
        for page in iam.get_paginator("list_users").paginate()
        for user in page["Users"]
    ]
    users = [
        _IamUserInfo(
            username=user["UserName"], keys=get_keys(username=user["UserName"])
        )
        for user in raw_users
    ]
    return sorted(users, key=lambda u: u.username)


def create_user(*, username: str) -> AwsProfile:
    """Create a new IAM user and an access key. Raises if the IAM user already exists."""
    iam = boto_client_iam()
    try:
        _ = iam.get_user(UserName=username)
        raise ValueError("IAM user '{}' already exists.".format(username))
    except iam.exceptions.NoSuchEntityException:
        pass

    _ = iam.create_user(UserName=username)
    key = iam.create_access_key(UserName=username)["AccessKey"]
    return AwsProfile(
        name=username,
        aws_access_key_id=key["AccessKeyId"],
        aws_secret_access_key=key["SecretAccessKey"],
    )


def rotate_key(*, username: str, protected_key_ids: set[str]) -> AwsProfile:
    """Create a new access key for an IAM user, deleting the previous key first if one exists.

    Raises ValueError if the previous key is in protected_key_ids.
    """
    existing = get_keys(username=username)
    if existing.previous is not None:
        delete_key(
            username=username,
            key_id=existing.previous.key_id,
            protected_key_ids=protected_key_ids,
        )

    iam = boto_client_iam()
    key = iam.create_access_key(UserName=username)["AccessKey"]
    return AwsProfile(
        name=username,
        aws_access_key_id=key["AccessKeyId"],
        aws_secret_access_key=key["SecretAccessKey"],
    )


def delete_key(*, username: str, key_id: str, protected_key_ids: set[str]) -> None:
    """Delete a specific access key for the IAM user.

    Raises ValueError if key_id is in protected_key_ids.
    """
    if key_id in protected_key_ids:
        raise ValueError("Refusing to delete protected key '{}'.".format(key_id))
    _ = boto_client_iam().delete_access_key(UserName=username, AccessKeyId=key_id)


def delete_user(*, username: str, protected_usernames: set[str]) -> None:
    """Delete an IAM user.

    Raises ValueError if the IAM user does not exist, still has access keys, or is protected.
    """
    if username in protected_usernames:
        raise ValueError("Refusing to delete protected IAM user '{}'.".format(username))
    iam = boto_client_iam()
    try:
        keys = iam.list_access_keys(UserName=username)["AccessKeyMetadata"]
    except iam.exceptions.NoSuchEntityException as exc:
        raise ValueError("IAM user '{}' not found.".format(username)) from exc
    if keys:
        raise ValueError("IAM user '{}' still has an access key.".format(username))
    _ = iam.delete_user(UserName=username)
