"""Typing helpers for cleanly annotating loosely-typed third-party APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client


def boto_client_s3(*, region: str) -> S3Client:
    """Obtain a boto3 S3 client for region."""
    return boto3.client(  # pyright: ignore[reportUnknownMemberType]
        "s3", region_name=region
    )
