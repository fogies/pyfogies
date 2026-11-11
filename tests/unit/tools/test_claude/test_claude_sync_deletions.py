"""Test deleting sessions on every machine that syncs them."""

import json
import pathlib
from collections.abc import Callable
from typing import cast

import pytest

from fogies.tools.boto import S3Object, S3PreconditionFailed
from fogies.tools.claude_sync import claude_directory
from fogies.tools.claude_sync_deletions import (
    _load,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync_deletions import (
    KEY,
    apply_deletion_locally,
    apply_deletions_locally,
    deleted_session_ids,
    record_deletion,
    record_desktop_deletions,
)

_ID = "60c0de8b-271f-4239-830d-bbe9838a631c"
_OTHER_ID = "f542028f-01b1-4734-ad54-e30e6b957005"
_THIRD_ID = "11111111-0000-4000-8000-000000000001"

_BUCKET = {"bucket_name": "bucket", "region": "us-west-2"}


def _uuid(number: int) -> str:
    """A session ID, which has to be a UUID, that sorts in the order of number."""
    return "00000000-0000-4000-8000-{:012d}".format(number)


class _FakeBucket:
    """A bucket of one object, with the conditional writes that S3 has."""

    body: bytes | None
    version: int
    # What runs just before each write, to be another machine's change.
    interference: list[Callable[[], None]]

    def __init__(self) -> None:
        self.body = None
        self.version = 0
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


def _marker(released_at: str, *, reason: str = "delete") -> str:
    """The marker that the Claude desktop app leaves for a deleted session."""
    return json.dumps({"v": 1, "releasedAt": released_at, "reason": reason})


def _write_marker(project: str, name: str, text: str) -> None:
    """Write a marker, which is named for the session it is for."""
    directory = claude_directory() / "projects" / project
    directory.mkdir(parents=True, exist_ok=True)
    _ = (directory / (name + ".desktop-released.json")).write_text(
        text, encoding="utf-8"
    )


def test_record_deletion_adds_to_what_is_recorded(bucket: _FakeBucket) -> None:
    """The first creates the record, and later ones add."""
    first = _uuid(1)
    second = _uuid(2)

    record_deletion(**_BUCKET, session_id=first)
    record_deletion(**_BUCKET, session_id=second)

    assert list(bucket.deleted()) == [first, second]
    assert deleted_session_ids(**_BUCKET) == {first, second}


@pytest.mark.parametrize(
    ("changes", "succeeds"),
    [(1, True), (10, False)],
    ids=["changed once", "keeps changing"],
)
def test_record_deletion_retries_if_the_record_changed_meanwhile(
    bucket: _FakeBucket, changes: int, succeeds: bool
) -> None:
    """A write is refused if the record changed, and is made again from the change."""
    this_deletion = _uuid(1)
    recorded_by_others = [_uuid(10 + i) for i in range(changes)]

    def another_machine_records(count: int) -> Callable[[], None]:
        return lambda: bucket.set(_record(*recorded_by_others[:count]))

    bucket.set(_record())
    # Each time this machine tries to write, another has recorded a deletion since
    # it read, until there are no more.
    bucket.interference.extend(another_machine_records(i + 1) for i in range(changes))

    if succeeds:
        record_deletion(**_BUCKET, session_id=this_deletion)

        assert set(bucket.deleted()) == {this_deletion, *recorded_by_others}
    else:
        with pytest.raises(RuntimeError, match="kept changing"):
            record_deletion(**_BUCKET, session_id=this_deletion)


@pytest.mark.parametrize(
    ("session", "understood"),
    [(_uuid(1), True), (_uuid(1)[:-1], False)],
    ids=["a UUID", "a UUID missing a digit"],
)
def test_load_understands_a_record_only_of_session_ids(
    bucket: _FakeBucket, session: str, understood: bool
) -> None:
    """What is not quite a session ID is not understood, as it is used in paths."""
    bucket.set(_record(session))

    if understood:
        record, _ = _load(**_BUCKET)
        assert list(record.deleted) == [session]
    else:
        with pytest.raises(ValueError, match="not a record of deleted sessions"):
            _ = _load(**_BUCKET)


def test_apply_deletions_locally_deletes_what_was_recorded(
    bucket: _FakeBucket, temp_home: pathlib.Path
) -> None:
    """The session and its subagents go, from whichever project, and others stay."""
    _ = temp_home
    # Recorded as deleted, and on this machine, with subagents.
    recorded_and_here = _uuid(1)
    # On this machine, but never recorded as deleted.
    not_recorded = _uuid(2)
    # Recorded as deleted, but never on this machine.
    recorded_not_here = _uuid(3)

    _write_session("project-1", recorded_and_here, subagents=True)
    _write_session("project-2", not_recorded)
    bucket.set(_record(recorded_and_here, recorded_not_here))

    # Only what was here is reported as deleted.
    assert apply_deletions_locally(**_BUCKET) == [recorded_and_here]

    assert not _exists("project-1", recorded_and_here)
    subagents = claude_directory() / "projects" / "project-1" / recorded_and_here
    assert not subagents.exists()
    assert _exists("project-2", not_recorded)
    # Still recorded, for machines that have not yet synced.
    assert set(bucket.deleted()) == {recorded_and_here, recorded_not_here}


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


def test_record_desktop_deletions_records_what_the_app_deleted(
    bucket: _FakeBucket, temp_home: pathlib.Path
) -> None:
    """Each is recorded as of when the app deleted it, whichever project it was in."""
    _ = temp_home
    _write_marker("project-b", _OTHER_ID, _marker("2026-10-27T21:00:00.000Z"))
    _write_marker("project-a", _ID, _marker("2026-10-27T20:45:00.000Z"))

    assert record_desktop_deletions(**_BUCKET) == [_ID, _OTHER_ID]

    assert bucket.deleted()[_ID]["at"] == "2026-10-27T20:45:00.000Z"
    assert bucket.deleted()[_OTHER_ID]["at"] == "2026-10-27T21:00:00.000Z"
    assert bucket.deleted()[_ID]["machine"]


@pytest.mark.parametrize(
    ("name", "text"),
    [
        (_ID, _marker("2026-10-27T20:45:00.000Z", reason="archive")),
        (_ID, json.dumps({"v": 1, "reason": "delete"})),
        (_ID, "["),
        (_ID, "[]"),
        ("notes", _marker("2026-10-27T20:45:00.000Z")),
    ],
    ids=["other reason", "no time", "not JSON", "not an object", "not for a session"],
)
def test_record_desktop_deletions_skips_what_is_not_a_deletion(
    bucket: _FakeBucket, temp_home: pathlib.Path, name: str, text: str
) -> None:
    _ = temp_home
    _write_marker("project-a", name, text)

    assert record_desktop_deletions(**_BUCKET) == []

    assert bucket.body is None


def test_record_desktop_deletions_leaves_what_is_already_recorded(
    bucket: _FakeBucket, temp_home: pathlib.Path
) -> None:
    """Nothing is written if there is nothing to add."""
    _ = temp_home
    bucket.set(_record(_ID))
    _write_marker("project-a", _ID, _marker("2026-10-27T20:45:00.000Z"))
    _write_marker("project-a", _OTHER_ID, _marker("2026-10-27T21:00:00.000Z"))

    assert record_desktop_deletions(**_BUCKET) == [_OTHER_ID]
    assert bucket.deleted()[_ID]["at"] == "2026-10-25T00:00:00+00:00"
    version = bucket.version

    assert record_desktop_deletions(**_BUCKET) == []
    assert bucket.version == version


@pytest.mark.usefixtures("bucket")
def test_record_desktop_deletions_without_any_markers(temp_home: pathlib.Path) -> None:
    """Without a projects directory, or with no markers in it, nothing is read."""
    _ = temp_home
    assert record_desktop_deletions(**_BUCKET) == []

    _write_session("project-a", _ID)
    assert record_desktop_deletions(**_BUCKET) == []


def test_record_desktop_deletions_keeps_what_another_machine_recorded_meanwhile(
    bucket: _FakeBucket, temp_home: pathlib.Path
) -> None:
    """Only what this recorded is returned, even if another recorded it first."""
    _ = temp_home
    bucket.set(_record(_THIRD_ID))
    _write_marker("project-a", _ID, _marker("2026-10-27T20:45:00.000Z"))
    _write_marker("project-a", _OTHER_ID, _marker("2026-10-27T21:00:00.000Z"))
    # Another machine records one of these, between this one reading and writing.
    bucket.interference.append(lambda: bucket.set(_record(_THIRD_ID, _OTHER_ID)))

    assert record_desktop_deletions(**_BUCKET) == [_ID]

    assert set(bucket.deleted()) == {_ID, _OTHER_ID, _THIRD_ID}
    assert bucket.deleted()[_OTHER_ID]["at"] == "2026-10-25T00:00:00+00:00"
