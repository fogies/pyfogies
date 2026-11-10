"""Deleting Claude Code sessions on every machine that syncs them.

A session deleted on one machine comes back from the others: the next push from
a machine that still has it uploads it again, and a pull downloads it to the
machine that deleted it. So a deletion is recorded in a bucket, and each machine,
after a pull, deletes what has been recorded. A session is deleted as the Claude
Agent SDK deletes one, which is its transcript and its subagents' transcripts.
To delete a session everywhere, record it, and then delete it from this machine,
so that if recording fails nothing is deleted.

The bucket is not the one claude-sync syncs to (see the claude_sync Terraform
module), because claude-sync owns the root of that bucket and deletes everything
in it when reset. The record is one object in it, KEY. It is changed only by a
write that is conditional on the object being as it was read, so that machines
that delete at the same time do not replace each other's deletions. The bucket
is versioned, so earlier versions of it can be recovered.

A session deleted in the Claude desktop app is recorded from the marker that the
app leaves, `<session ID>.desktop-released.json` in the project, which claude-sync
syncs. A marker is only a signal to record it, as the app removes it from a
session it brings back, so the record is what a deletion is kept in.

These use the AWS credentials of the environment, which the caller applies
(e.g., with fogies.tools.aws_environ.aws_environ_from_config).
"""

import datetime
import socket
import uuid
from collections.abc import Callable
from typing import Literal

from claude_agent_sdk import delete_session
from pydantic import BaseModel, Field, ValidationError

from fogies.tools.boto import S3PreconditionFailed, s3_get_object, s3_put_object
from fogies.tools.claude_sync import claude_directory

# Where the record is, in the bucket.
KEY = "deleted-sessions.json"

_FORMAT = "pyfogies-deleted-sessions"
_WRITTEN_BY = "fogies.tools.claude_sync_deletions"

# What the end of the name of a marker is, for the Claude desktop app.
_MARKER_SUFFIX = ".desktop-released.json"

# How many times a change is tried, if others are changing the record too.
_ATTEMPTS = 5


class _Deletion(BaseModel):
    """When, and from which machine, a session was deleted."""

    at: str
    machine: str


class _DesktopMarker(BaseModel):
    """What the Claude desktop app leaves when a session is deleted in it.

    Only a deletion is of use here, and the rest of what is in it is ignored.
    """

    reason: Literal["delete"]
    released_at: str = Field(alias="releasedAt")


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


def _update(
    *,
    bucket_name: str,
    region: str,
    change: Callable[[_DeletedSessions], None],
) -> None:
    """Change the record, which is not written if the change leaves it as it was.

    The change is made to the record as it is, and made again to the record as
    it then is if others changed it meanwhile, so it must not depend on being
    called once. Raises ValueError if what is in the bucket is not understood.
    Raises RuntimeError if others kept changing the record, so that this could
    not.
    """
    for _ in range(_ATTEMPTS):
        record, etag = _load(bucket_name=bucket_name, region=region)
        before = record.model_copy(deep=True)
        change(record)
        if record == before:
            return
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
    raise RuntimeError("Could not change '{}', as it kept changing.".format(KEY))


def record_deletion(*, bucket_name: str, region: str, session_id: str) -> None:
    """Record a session as deleted, for the machines that sync it.

    Raises ValueError if session_id is not a session ID, or if what is in the
    bucket is not understood. Raises RuntimeError if others kept changing the
    record, so that this could not.
    """
    valid_id = _require_session_id(session_id)

    def add(record: _DeletedSessions) -> None:
        record.deleted[valid_id] = _Deletion(
            at=datetime.datetime.now().astimezone().isoformat(),
            machine=socket.gethostname(),
        )

    _update(bucket_name=bucket_name, region=region, change=add)


def _desktop_deletions() -> dict[str, _Deletion]:
    """Return the sessions that were deleted in the Claude desktop app.

    The app leaves a marker for each, in the project that had the session.
    Anything else in that place, or that is not as expected, is skipped.
    """
    deletions: dict[str, _Deletion] = {}
    for path in (claude_directory() / "projects").glob("*/*" + _MARKER_SUFFIX):
        session_id = _session_id(path.name.removesuffix(_MARKER_SUFFIX))
        if session_id is None:
            continue
        try:
            marker = _DesktopMarker.model_validate_json(path.read_bytes())
        except OSError, ValidationError:
            continue
        deletions[session_id] = _Deletion(
            at=marker.released_at, machine=socket.gethostname()
        )
    return deletions


def record_desktop_deletions(*, bucket_name: str, region: str) -> list[str]:
    """Record the sessions that were deleted in the Claude desktop app.

    Those that are already recorded are left as they are. Returns the IDs of
    the sessions that were recorded, and writes nothing if there are none.
    Raises ValueError if what is in the bucket is not understood. Raises
    RuntimeError if others kept changing the record, so that this could not.
    """
    deletions = _desktop_deletions()
    if not deletions:
        return []

    recorded: list[str] = []

    def add(record: _DeletedSessions) -> None:
        recorded.clear()
        for session_id, deletion in deletions.items():
            if session_id not in record.deleted:
                record.deleted[session_id] = deletion
                recorded.append(session_id)

    _update(bucket_name=bucket_name, region=region, change=add)
    return sorted(recorded)


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
