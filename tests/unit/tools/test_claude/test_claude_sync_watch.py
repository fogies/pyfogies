"""Test when claude-sync is synced while watching."""

import os
import pathlib
import subprocess
import sys
import time
from typing import cast

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
        # Nothing has changed since the last sync, and the interval has not passed.
        (1200.0, None, False),
        (1200.0, 900.0, False),
        # A change since the last sync is waited on until it has been quiet.
        (1150.0, 1100.0, False),
        (1220.0, 1100.0, True),
        # Changes that continue wait no longer than the interval.
        (1299.0, 1290.0, False),
        (1300.0, 1299.0, True),
        # With nothing changed, the interval passing is enough to bring in changes.
        (1300.0, None, True),
    ],
    ids=[
        "never changed",
        "changed before",
        "changed recently",
        "changed and quiet",
        "still changing",
        "still changing past interval",
        "interval",
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


def test_sync_due_ignores_what_the_sync_wrote() -> None:
    """A change by the sync itself is not one to sync, however quiet it has been."""
    assert not sync_due(
        now=1200.0,
        newest_change=1050.0,
        # The newest change as of the end of a sync that began at 1000.
        synced_change=1050.0,
        last_sync=1000.0,
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


def test_only_one_watch_across_processes(temp_home: pathlib.Path) -> None:
    """Another process's watch is seen, and is not once that process is gone.

    The lock is released by the operating system, so a watch that is killed
    does not leave one behind to refuse the next.
    """
    home = str(temp_home)
    holds_the_lock = "; ".join(
        [
            "from fogies.tools.claude_sync_watch import _watch_lock",
            "lock = _watch_lock()",
            "lock.__enter__()",
            "print('holding', flush=True)",
            "input()",
        ]
    )
    holder: subprocess.Popen[str] = subprocess.Popen(
        [sys.executable, "-c", holds_the_lock],
        env={**os.environ, "HOME": home, "USERPROFILE": home},
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        first_line = cast(str, holder.stdout.readline())
        assert first_line.strip() == "holding"

        assert is_watching()
        with pytest.raises(ValueError, match="already being watched"):
            with _watch_lock():
                pass

        # Killed, so not asked to release it. Windows releases it shortly after
        # the process is gone, not at the same moment.
        holder.kill()
        _ = holder.wait(timeout=10)
        deadline = time.monotonic() + 10
        while is_watching() and time.monotonic() < deadline:
            time.sleep(0.05)

        assert not is_watching()
    finally:
        holder.kill()
        _ = holder.wait(timeout=10)
        if holder.stdin is not None:
            holder.stdin.close()
        if holder.stdout is not None:
            holder.stdout.close()
