"""Test when claude-sync is synced while watching."""

import os
import pathlib

import pytest

from fogies.tools.claude_sync_watch import (
    _watch_lock,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync_watch import (
    is_watching,
    newest_change,
    sync_due,
)

# A sync at time 1000, with the newest change then also at 1000, and what
# happens as time passes.
_LAST_SYNC = 1000.0
_SYNCED_CHANGE = 1000.0
_QUIET = 120.0
_INTERVAL = 300.0


@pytest.mark.parametrize(
    ("now", "changed", "due"),
    [
        # Nothing to sync: no change at all, or none but what the sync itself
        # wrote, which is the newest change as of the end of the sync, however
        # quiet it has been since.
        (1200.0, None, False),
        (1200.0, 1000.0, False),
        # A change since the last sync is waited on until it has been quiet,
        # whether it was made once or is still being made, until the interval.
        (1150.0, 1100.0, False),
        (1220.0, 1100.0, True),
        # Changes that continue wait no longer than the interval.
        (1300.0, 1299.0, True),
    ],
    ids=[
        "never changed",
        "changed by the sync itself",
        "changed recently",
        "changed and quiet",
        "still changing past interval",
    ],
)
def test_sync_due(now: float, changed: float | None, due: bool) -> None:
    assert (
        sync_due(
            now=now,
            newest_change=changed,
            synced_change=_SYNCED_CHANGE,
            last_sync=_LAST_SYNC,
            quiet_seconds=_QUIET,
            interval_seconds=_INTERVAL,
        )
        is due
    )


def test_sync_due_for_the_first_file_to_exist() -> None:
    """A file that appears after a sync that found none is a change to sync."""
    assert sync_due(
        now=1220.0,
        newest_change=1100.0,
        # There were no files as of the end of the last sync.
        synced_change=None,
        last_sync=_LAST_SYNC,
        quiet_seconds=_QUIET,
        interval_seconds=_INTERVAL,
    )


def test_newest_change(tmp_path: pathlib.Path) -> None:
    """The newest change among what is polled, and nothing else, is found."""
    assert newest_change(directory=tmp_path) is None

    project = tmp_path / "projects" / "demo"
    project.mkdir(parents=True)
    session = project / "a.jsonl"
    _ = session.write_text("a", encoding="utf-8")
    os.utime(session, (100, 100))
    history = tmp_path / "history.jsonl"
    _ = history.write_text("h", encoding="utf-8")
    os.utime(history, (200, 200))
    # Not polled, however recent.
    other = tmp_path / "plugins" / "p.txt"
    other.parent.mkdir()
    _ = other.write_text("p", encoding="utf-8")
    os.utime(other, (900, 900))
    # Directories are older than the files they were made for.
    for directory in (project, project.parent):
        os.utime(directory, (50, 50))

    assert newest_change(directory=tmp_path) == 200

    # A file that is deleted changes its directory, which is also a change.
    session.unlink()
    newest = newest_change(directory=tmp_path)
    assert newest is not None and newest > 200


def test_only_one_watch_in_a_process(temp_home: pathlib.Path) -> None:
    """A second watch is refused while the first has the lock, and not after."""
    _ = temp_home
    assert not is_watching()

    with _watch_lock():
        assert is_watching()
        with pytest.raises(ValueError, match="already being watched"):
            with _watch_lock():
                pass

    assert not is_watching()
