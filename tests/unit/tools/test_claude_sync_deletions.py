"""Test deleting sessions on every machine that syncs them."""

import json
import pathlib
from collections.abc import Callable
from typing import cast

import pytest

from fogies.tools.boto import S3Object, S3PreconditionFailed
from fogies.tools.claude_sync import claude_directory
from fogies.tools.claude_sync_deletions import (
    KEY,
    apply_deletion_locally,
    apply_deletions_locally,
    deleted_session_ids,
    record_deletion,
)

_ID = "60c0de8b-271f-4239-830d-bbe9838a631c"
_OTHER_ID = "f542028f-01b1-4734-ad54-e30e6b957005"
_THIRD_ID = "11111111-0000-4000-8000-000000000001"

_BUCKET = {"bucket_name": "bucket", "region": "us-west-2"}


class _FakeBucket:
    """A bucket of one object, with the conditional writes that S3 has."""

    body: bytes | None
    version: int
    metadata: dict[str, str]
    # What runs just before each write, to be another machine's change.
    interference: list[Callable[[], None]]

    def __init__(self) -> None:
        self.body = None
        self.version = 0
        self.metadata = {}
        self.interference = []

    @property
    def etag(self) -> str | None:
        return None if self.body is None else '"{}"'.format(self.version)

    def set(self, record: object) -> None:
        """Replace the object, as another machine would."""
        self.body = json.dumps(record).encode("utf-8")
        self.version += 1

    def get(self, *, bucket_name: str, region: str, key: str) -> S3Object | None:
        assert (bucket_name, region, key) == ("bucket", "us-west-2", KEY)
        if self.body is None or self.etag is None:
            return None
        return S3Object(body=self.body, etag=self.etag)

    def put(
        self,
        *,
        bucket_name: str,
        region: str,
        key: str,
        body: bytes,
        if_match: str | None = None,
        if_absent: bool = False,
        metadata: dict[str, str] | None = None,
    ) -> str:
        assert (bucket_name, region, key) == ("bucket", "us-west-2", KEY)
        if self.interference:
            self.interference.pop(0)()
        if if_absent and self.body is not None:
            raise S3PreconditionFailed("exists")
        if if_match is not None and if_match != self.etag:
            raise S3PreconditionFailed("changed")
        self.body = body
        self.version += 1
        self.metadata = metadata or {}
        assert self.etag is not None
        return self.etag

    def deleted(self) -> dict[str, dict[str, str]]:
        assert self.body is not None
        record = cast(dict[str, object], json.loads(self.body))
        return cast(dict[str, dict[str, str]], record["deleted"])


@pytest.fixture
def bucket(monkeypatch: pytest.MonkeyPatch) -> _FakeBucket:
    fake = _FakeBucket()
    monkeypatch.setattr("fogies.tools.claude_sync_deletions.s3_get_object", fake.get)
    monkeypatch.setattr("fogies.tools.claude_sync_deletions.s3_put_object", fake.put)
    return fake


def _record(*session_ids: str) -> dict[str, object]:
    """A record, as another machine would have written it."""
    return {
        "format": "pyfogies-deleted-sessions",
        "version": 1,
        "deleted": {
            i: {"at": "2026-10-25T00:00:00+00:00", "machine": "other"}
            for i in session_ids
        },
    }


def _write_session(project: str, session_id: str, *, subagents: bool = False) -> None:
    """Write a session's transcript, and optionally its subagents' directory."""
    directory = claude_directory() / "projects" / project
    directory.mkdir(parents=True, exist_ok=True)
    _ = (directory / (session_id + ".jsonl")).write_text("{}\n", encoding="utf-8")
    if subagents:
        subagent = directory / session_id / "subagents" / "agent.jsonl"
        subagent.parent.mkdir(parents=True)
        _ = subagent.write_text("{}\n", encoding="utf-8")


def _exists(project: str, session_id: str) -> bool:
    directory = claude_directory() / "projects" / project
    return (directory / (session_id + ".jsonl")).exists()


def test_record_deletion_adds_to_what_is_recorded(bucket: _FakeBucket) -> None:
    """The first creates the record, saying what wrote it, and later ones add."""
    record_deletion(**_BUCKET, session_id=_ID)
    record_deletion(**_BUCKET, session_id=_OTHER_ID.upper())

    assert list(bucket.deleted()) == [_ID, _OTHER_ID]
    assert bucket.deleted()[_ID]["machine"]
    assert bucket.metadata == {"written-by": "fogies.tools.claude_sync_deletions"}
    assert deleted_session_ids(**_BUCKET) == {_ID, _OTHER_ID}


def test_record_deletion_keeps_what_another_machine_recorded_meanwhile(
    bucket: _FakeBucket,
) -> None:
    """A write is refused if the record changed, and is made again from the change."""
    bucket.set(_record(_THIRD_ID))
    # Another machine records its deletion between this one reading and writing.
    bucket.interference.append(lambda: bucket.set(_record(_THIRD_ID, _OTHER_ID)))

    record_deletion(**_BUCKET, session_id=_ID)

    assert set(bucket.deleted()) == {_ID, _OTHER_ID, _THIRD_ID}


def test_record_deletion_gives_up_if_the_record_keeps_changing(
    bucket: _FakeBucket,
) -> None:
    bucket.set(_record())
    bucket.interference.extend(lambda: bucket.set(_record()) for _ in range(10))

    with pytest.raises(RuntimeError, match="kept changing"):
        record_deletion(**_BUCKET, session_id=_ID)


@pytest.mark.parametrize(
    "record",
    [
        {"format": "something-else", "version": 1, "deleted": {}},
        {"format": "pyfogies-deleted-sessions", "version": 2, "deleted": {}},
        {"format": "pyfogies-deleted-sessions", "version": 1, "deleted": [_ID]},
    ],
    ids=["other format", "other version", "other shape"],
)
def test_a_record_that_is_not_understood_is_not_used_or_changed(
    bucket: _FakeBucket, temp_home: pathlib.Path, record: object
) -> None:
    _ = temp_home
    bucket.set(record)
    before = bucket.body
    _write_session("project-a", _ID)

    with pytest.raises(ValueError, match="not a record of deleted sessions"):
        _ = deleted_session_ids(**_BUCKET)
    with pytest.raises(ValueError, match="not a record of deleted sessions"):
        _ = apply_deletions_locally(**_BUCKET)
    with pytest.raises(ValueError, match="not a record of deleted sessions"):
        record_deletion(**_BUCKET, session_id=_OTHER_ID)

    assert bucket.body == before
    assert _exists("project-a", _ID)


def test_ids_that_are_not_session_ids_are_not_used(bucket: _FakeBucket) -> None:
    """What is in the bucket is used in paths, so is not trusted."""
    bucket.set(_record("../../../outside", "*", _ID))

    assert deleted_session_ids(**_BUCKET) == {_ID}


def test_record_deletion_of_what_is_not_a_session_id(bucket: _FakeBucket) -> None:
    with pytest.raises(ValueError, match="not a session ID"):
        record_deletion(**_BUCKET, session_id="../outside")

    assert bucket.body is None


def test_apply_deletions_locally_deletes_what_was_recorded(
    bucket: _FakeBucket, temp_home: pathlib.Path
) -> None:
    """The session and its subagents go, from whichever project, and others stay."""
    _ = temp_home
    _write_session("project-b", _ID, subagents=True)
    _write_session("project-a", _OTHER_ID)
    # Recorded, but never here.
    bucket.set(_record(_ID, _THIRD_ID))

    assert apply_deletions_locally(**_BUCKET) == [_ID]

    assert not _exists("project-b", _ID)
    assert not (claude_directory() / "projects" / "project-b" / _ID).exists()
    assert _exists("project-a", _OTHER_ID)
    # Still recorded, for machines that have not yet synced.
    assert set(bucket.deleted()) == {_ID, _THIRD_ID}


@pytest.mark.usefixtures("bucket")
def test_apply_deletions_locally_with_nothing_recorded(temp_home: pathlib.Path) -> None:
    _ = temp_home
    _write_session("project-a", _ID)

    assert apply_deletions_locally(**_BUCKET) == []

    assert _exists("project-a", _ID)


def test_apply_deletion_locally_deletes_only_that_session(
    temp_home: pathlib.Path,
) -> None:
    """It is found from an ID in any case, and a second time it is not here."""
    _ = temp_home
    _write_session("project-a", _ID, subagents=True)
    _write_session("project-a", _OTHER_ID)

    assert apply_deletion_locally(_ID.upper())
    assert not apply_deletion_locally(_ID)

    assert not _exists("project-a", _ID)
    assert not (claude_directory() / "projects" / "project-a" / _ID).exists()
    assert _exists("project-a", _OTHER_ID)


def test_apply_deletion_locally_of_what_is_not_a_session_id() -> None:
    with pytest.raises(ValueError, match="not a session ID"):
        _ = apply_deletion_locally("../outside")
