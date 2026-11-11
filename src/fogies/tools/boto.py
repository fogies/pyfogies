"""Generic boto3-based tools, not specific to any particular use case."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError

from fogies.boto_clients import boto_client_s3

if TYPE_CHECKING:
    from mypy_boto3_s3.type_defs import (
        ErrorTypeDef,
        ObjectIdentifierTypeDef,
        PutObjectRequestTypeDef,
    )


def s3_delete_keys(*, bucket_name: str, region: str, keys: set[str]) -> None:
    """Delete every version and delete marker for keys, from bucket_name.

    Keys not present in the bucket are silently ignored. Lists each key's
    versions individually (scoped by prefix), rather than scanning the whole
    bucket, so this stays cheap even for buckets holding many unrelated
    objects. Works whether or not the bucket has versioning enabled: an
    unversioned object is listed with a "null" version id, which deletes it
    normally. Raises RuntimeError if any deletion fails.
    """
    if not keys:
        return

    client = boto_client_s3(region=region)

    objects_to_delete: list[ObjectIdentifierTypeDef] = []
    paginator = client.get_paginator("list_object_versions")
    for key in keys:
        for page in paginator.paginate(Bucket=bucket_name, Prefix=key):
            for version in page.get("Versions") or []:
                version_key = version.get("Key")
                version_id = version.get("VersionId")
                if (
                    version_key is not None
                    and version_id is not None
                    and version_key == key
                ):
                    objects_to_delete.append(
                        {"Key": version_key, "VersionId": version_id}
                    )
            for marker in page.get("DeleteMarkers") or []:
                marker_key = marker.get("Key")
                version_id = marker.get("VersionId")
                if (
                    marker_key is not None
                    and version_id is not None
                    and marker_key == key
                ):
                    objects_to_delete.append(
                        {"Key": marker_key, "VersionId": version_id}
                    )

    errors: list[ErrorTypeDef] = []
    for i in range(0, len(objects_to_delete), 1000):
        response = client.delete_objects(
            Bucket=bucket_name,
            Delete={"Objects": objects_to_delete[i : i + 1000]},
        )
        errors.extend(response.get("Errors") or [])

    if errors:
        raise RuntimeError(
            "Failed to delete {} object(s) from bucket '{}':\n{}".format(
                len(errors),
                bucket_name,
                json.dumps(errors, indent=2),
            )
        )


@dataclass(frozen=True)
class S3Object:
    """An object read from S3, and the ETag that identifies this version of it."""

    body: bytes
    etag: str


class S3PreconditionFailed(Exception):
    """A write was refused, as the object is not as the write needed it to be."""


def s3_get_object(*, bucket_name: str, region: str, key: str) -> S3Object | None:
    """Read key from bucket_name, or return None if it does not exist."""
    client = boto_client_s3(region=region)
    try:
        response = client.get_object(Bucket=bucket_name, Key=key)
    except client.exceptions.NoSuchKey:
        return None
    return S3Object(body=response["Body"].read(), etag=response["ETag"])


def s3_put_object(
    *,
    bucket_name: str,
    region: str,
    key: str,
    body: bytes,
    if_match: str | None = None,
    if_absent: bool = False,
) -> str:
    """Write body to key in bucket_name, and return the new ETag.

    With *if_match*, the write is only made if the object has that ETag, as
    read earlier, so that it does not replace a change made since. With
    *if_absent*, only if there is no such object. Raises S3PreconditionFailed
    if not, including if another write was in progress, or if the object is
    gone, and the caller can read it again and retry.
    """
    if if_match is not None and if_absent:
        raise ValueError("Give if_match, or if_absent, and not both.")

    request: PutObjectRequestTypeDef = {
        "Bucket": bucket_name,
        "Key": key,
        "Body": body,
    }
    if if_match is not None:
        request["IfMatch"] = if_match
    if if_absent:
        request["IfNoneMatch"] = "*"

    client = boto_client_s3(region=region)
    try:
        response = client.put_object(**request)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("PreconditionFailed", "ConditionalRequestConflict", "NoSuchKey"):
            raise S3PreconditionFailed(
                "'{}' is not as it was expected to be.".format(key)
            ) from exc
        raise
    return response["ETag"]
