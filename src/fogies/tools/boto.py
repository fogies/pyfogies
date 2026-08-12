"""Generic boto3-based tools, not specific to any particular use case."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fogies.typing import boto_client_s3

if TYPE_CHECKING:
    from mypy_boto3_s3.type_defs import ErrorTypeDef, ObjectIdentifierTypeDef


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
