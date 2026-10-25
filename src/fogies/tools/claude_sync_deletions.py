"""Deleting Claude Code sessions on every machine that syncs them.

A session deleted on one machine comes back from the others: the next push from
a machine that still has it uploads it again, and a pull downloads it to the
machine that deleted it. So a deletion is recorded in the bucket claude-sync
syncs to, and each machine, after a pull, deletes what has been recorded.

The record is one object in the bucket, KEY, which claude-sync ignores, as it
only reads objects with an `.age` suffix. It is changed only by a write that
is conditional on the object being as it was read, so that machines that delete
at the same time do not replace each other's deletions. The bucket is
versioned, so earlier versions of it can be recovered.

These use the AWS credentials of the environment, which the caller applies
(e.g., with fogies.tools.aws_environ.aws_environ_from_config).
"""

import datetime
import shutil
import socket
import uuid
from typing import Literal

from pydantic import BaseModel, ValidationError

from fogies.tools.boto import S3PreconditionFailed, s3_get_object, s3_put_object
from fogies.tools.claude_sync import claude_directory

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
    valid_id = _session_id(session_id)
    if valid_id is None:
        raise ValueError("'{}' is not a session ID.".format(session_id))

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


def _session_names(session_id: str) -> list[str]:
    """Return what is in the Claude directory for a session, as paths relative to it.

    That is its transcript, and the directory of its subagents' transcripts,
    in whichever projects have them.
    """
    projects = claude_directory() / "projects"
    names: list[str] = []
    if not projects.is_dir():
        return names
    for project in projects.iterdir():
        if not project.is_dir():
            continue
        for name in (session_id + ".jsonl", session_id):
            if (project / name).exists():
                names.append("projects/{}/{}".format(project.name, name))
    return names


def _remove(names: list[str]) -> None:
    """Delete paths relative to the Claude directory."""
    claude = claude_directory()
    for name in names:
        path = claude / name
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


def apply_deletions(*, bucket_name: str, region: str) -> list[str]:
    """Delete the sessions that have been recorded as deleted.

    Those that are already gone from here are skipped. Returns the IDs of the
    sessions that were deleted.
    """
    deleted: list[str] = []
    for session_id in sorted(
        deleted_session_ids(bucket_name=bucket_name, region=region)
    ):
        names = _session_names(session_id)
        if names:
            _remove(names)
            deleted.append(session_id)
    return deleted


def delete_everywhere(*, bucket_name: str, region: str, session_id: str) -> None:
    """Record a session as deleted, then delete it from this machine.

    The other machines delete it when they next sync. It is recorded first,
    so that if that fails nothing is deleted. Raises what record_deletion() does.
    """
    record_deletion(bucket_name=bucket_name, region=region, session_id=session_id)
    valid_id = _session_id(session_id)
    assert valid_id is not None
    _remove(_session_names(valid_id))
