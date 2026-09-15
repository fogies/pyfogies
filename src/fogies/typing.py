"""Typing helpers for cleanly annotating loosely-typed third-party APIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3

if TYPE_CHECKING:
    from mypy_boto3_ec2.client import EC2Client
    from mypy_boto3_ecs.client import ECSClient
    from mypy_boto3_iam.client import IAMClient
    from mypy_boto3_logs.client import CloudWatchLogsClient
    from mypy_boto3_s3.client import S3Client
    from mypy_boto3_sts.client import STSClient


# Each factory below creates its own boto3.Session() rather than using the
# boto3.client(...) module function. That function reuses a single implicit
# default session for the whole process, and botocore resolves credentials on
# a session once and caches them — so once anything creates a client via
# boto3.client(...), later calls keep using those same credentials even if
# AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY change afterward (e.g. between two
# environ()-scoped credential contexts in one process). A fresh Session per
# call re-resolves credentials from the current environment every time.


def boto_client_ec2(*, region: str) -> EC2Client:
    """Obtain a boto3 EC2 client for region."""
    return boto3.Session().client(  # pyright: ignore[reportUnknownMemberType]
        "ec2", region_name=region
    )


def boto_client_ecs(*, region: str) -> ECSClient:
    """Obtain a boto3 ECS client for region."""
    return boto3.Session().client(  # pyright: ignore[reportUnknownMemberType]
        "ecs", region_name=region
    )


def boto_client_logs(*, region: str) -> CloudWatchLogsClient:
    """Obtain a boto3 CloudWatch Logs client for region."""
    return boto3.Session().client(  # pyright: ignore[reportUnknownMemberType]
        "logs", region_name=region
    )


def boto_client_s3(*, region: str) -> S3Client:
    """Obtain a boto3 S3 client for region."""
    return boto3.Session().client(  # pyright: ignore[reportUnknownMemberType]
        "s3", region_name=region
    )


def boto_client_iam() -> IAMClient:
    """Obtain a boto3 IAM client from ambient environment credentials."""
    return boto3.Session().client("iam")  # pyright: ignore[reportUnknownMemberType]


def boto_client_sts() -> STSClient:
    """Obtain a boto3 STS client from ambient environment credentials."""
    return boto3.Session().client("sts")  # pyright: ignore[reportUnknownMemberType]
