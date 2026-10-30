"""Deleting Claude Code sessions on every machine that syncs them.

A session deleted on one machine comes back from the others: the next push from
a machine that still has it uploads it again, and a pull downloads it to the
machine that deleted it. So a deletion is recorded in the bucket claude-sync
syncs to, and each machine, after a pull, deletes what has been recorded. A
session is deleted as the Claude Agent SDK deletes one, which is its transcript
and its subagents' transcripts. To delete a session everywhere, record it, and
then delete it from this machine, so that if recording fails nothing is deleted.

The record is one object in the bucket, KEY, which claude-sync ignores, as it
only reads objects with an `.age` suffix. It is changed only by a write that
is conditional on the object being as it was read, so that machines that delete
at the same time do not replace each other's deletions. The bucket is
versioned, so earlier versions of it can be recovered.

These use the AWS credentials of the environment, which the caller applies
(e.g., with fogies.tools.aws_environ.aws_environ_from_config).
"""

import datetime
import socket
import uuid
from typing import Literal

from claude_agent_sdk import delete_session
from pydantic import BaseModel, ValidationError

from fogies.tools.boto import S3PreconditionFailed, s3_get_object, s3_put_object

# Where the record is, in the bucket. Under a name that says what wrote it.
KEY = "pyfogies/claude-sync/deleted-sessions.json"

_FORMAT = "pyfogies-deleted-sessions"
_WRITTEN_BY = "fogies.tools.claude_sync_deletions"

# How many times a change is tried, if others are changing the record too.
_ATTEMPTS = 5


class _Deletion(BaseModel):
    """When, and from which machine, a session was deleted."""

    at: str
    machine: str


class _DeletedSessions(BaseModel):
    """What is in the object. What is not this format is not changed or acted on."""

    format: Literal["pyfogies-deleted-sessions"] = _FORMAT
    version: Literal[1] = 1
    deleted: dict[str, _Deletion] = {}


def _session_id(value: str) -> str | None:
    """Return value as a session ID, or None if it is not one.

    The record comes from a bucket, and what is in it is used in paths, so only
    what is a UUID is used.
    """
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


def _require_session_id(value: str) -> str:
    """Return value as a session ID, or raise ValueError if it is not one."""
    session_id = _session_id(value)
    if session_id is None:
        raise ValueError("'{}' is not a session ID.".format(value))
    return session_id


def _load(*, bucket_name: str, region: str) -> tuple[_DeletedSessions, str | None]:
    """Return the record, and its ETag, which is None if there is no record yet.

    Raises ValueError if the object is not a record that this understands.
    """
    existing = s3_get_object(bucket_name=bucket_name, region=region, key=KEY)
    if existing is None:
        return _DeletedSessions(), None
    try:
        return _DeletedSessions.model_validate_json(existing.body), existing.etag
    except ValidationError as exc:
        raise ValueError(
            "'{}' in bucket '{}' is not a record of deleted sessions that is understood, so nothing is done with it: {}".format(
                KEY, bucket_name, exc
            )
        ) from exc


def deleted_session_ids(*, bucket_name: str, region: str) -> set[str]:
    """Return the IDs of the sessions that have been recorded as deleted.

    Anything in the record that is not a session ID is skipped.
    """
    record, _ = _load(bucket_name=bucket_name, region=region)
    return {i for i in map(_session_id, record.deleted) if i is not None}


def record_deletion(*, bucket_name: str, region: str, session_id: str) -> None:
    """Record a session as deleted, for the machines that sync it.

    Raises ValueError if session_id is not a session ID, or if what is in the
    bucket is not understood. Raises RuntimeError if others kept changing the
    record, so that this could not.
    """
    valid_id = _require_session_id(session_id)

    for _ in range(_ATTEMPTS):
        record, etag = _load(bucket_name=bucket_name, region=region)
        record.deleted[valid_id] = _Deletion(
            at=datetime.datetime.now().astimezone().isoformat(),
            machine=socket.gethostname(),
        )
        try:
            _ = s3_put_object(
                bucket_name=bucket_name,
                region=region,
                key=KEY,
                body=record.model_dump_json(indent=2).encode("utf-8"),
                if_match=etag,
                if_absent=etag is None,
                metadata={"written-by": _WRITTEN_BY},
            )
        except S3PreconditionFailed:
            # Changed since it was read, so read it again.
            continue
        return
    raise RuntimeError(
        "Could not record the deletion, as '{}' kept changing.".format(KEY)
    )


def apply_deletion_locally(session_id: str) -> bool:
    """Delete a session from this machine, and return whether it was here.

    Raises ValueError if session_id is not a session ID.
    """
    try:
        delete_session(_require_session_id(session_id))
    except FileNotFoundError:
        return False
    return True


def apply_deletions_locally(*, bucket_name: str, region: str) -> list[str]:
    """Delete from this machine the sessions that have been recorded as deleted.

    Those that are already gone from here are skipped. Returns the IDs of the
    sessions that were deleted.
    """
    return [
        session_id
        for session_id in sorted(
            deleted_session_ids(bucket_name=bucket_name, region=region)
        )
        if apply_deletion_locally(session_id)
    ]
