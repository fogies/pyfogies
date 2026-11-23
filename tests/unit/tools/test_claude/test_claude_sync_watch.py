"""Test when claude-sync is synced while watching."""

import math
import os
import pathlib
from collections.abc import Callable

import pytest

from fogies.tools.claude_sync import claude_directory
from fogies.tools.claude_sync_watch import (
    _INTERVAL_SECONDS,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync_watch import (
    _POLL_SECONDS,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync_watch import (
    _QUIET_SECONDS,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync_watch import (
    _RETRY_SECONDS,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync_watch import (
    _watch_lock,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync_watch import (
    is_watching,
    newest_change,
    sync_due,
    watch_and_sync,
)

# A sync at time 1000, with the newest change then also at 1000, and what
# happens as time passes.
_LAST_SYNC = 1000.0
_SYNCED_CHANGE = 1000.0
_QUIET = 120.0
_INTERVAL = 300.0
_RETRY = 60.0


@pytest.mark.parametrize(
    ("now", "changed", "last_attempt", "due"),
    [
        # Nothing to sync: no change at all, or none but what the sync itself
        # wrote, which is the newest change as of the end of the sync, however
        # quiet it has been since.
        (1200.0, None, _LAST_SYNC, False),
        (1200.0, 1000.0, _LAST_SYNC, False),
        # A change since the last sync is waited on until it has been quiet,
        # whether it was made once or is still being made, until the interval.
        (1150.0, 1100.0, _LAST_SYNC, False),
        (1220.0, 1100.0, _LAST_SYNC, True),
        # Changes that continue wait no longer than the interval.
        (1300.0, 1299.0, _LAST_SYNC, True),
        # After an attempt that failed, the last sync is still the earlier one, so
        # what was due still is, but not until the retry delay has passed.
        (1320.0, 1100.0, 1300.0, False),
        (1360.0, 1100.0, 1300.0, True),
    ],
    ids=[
        "never changed",
        "changed by the sync itself",
        "changed recently",
        "changed and quiet",
        "still changing past interval",
        "just failed",
        "failed a retry delay ago",
    ],
)
def test_sync_due(
    now: float, changed: float | None, last_attempt: float, due: bool
) -> None:
    assert (
        sync_due(
            now=now,
            newest_change=changed,
            synced_change=_SYNCED_CHANGE,
            last_sync=_LAST_SYNC,
            last_attempt=last_attempt,
            quiet_seconds=_QUIET,
            interval_seconds=_INTERVAL,
            retry_seconds=_RETRY,
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
        last_attempt=_LAST_SYNC,
        quiet_seconds=_QUIET,
        interval_seconds=_INTERVAL,
        retry_seconds=_RETRY,
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


def test_newest_change_finds_a_file_however_deep(tmp_path: pathlib.Path) -> None:
    """A session's subagents are in directories under it, which are looked in too."""
    shallow = tmp_path / "projects" / "demo" / "a.jsonl"
    deep = tmp_path / "projects" / "demo" / "a" / "subagents" / "agent.jsonl"
    deep.parent.mkdir(parents=True)
    for path, modified in ((shallow, 100), (deep, 300)):
        _ = path.write_text("{}", encoding="utf-8")
        os.utime(path, (modified, modified))
    # Directories are older than the files they were made for.
    for directory in tmp_path.rglob("*"):
        if directory.is_dir():
            os.utime(directory, (50, 50))

    assert newest_change(directory=tmp_path) == 300


class _Clock:
    """Stands in for the time module, which passes by sleeping, and stops the watch."""

    _now: float
    _sleeps_left: int
    _step: float
    # What runs after each sleep, given the time, to be what happens meanwhile.
    on_sleep: Callable[[float], None] | None

    def __init__(self, *, sleeps: int, step: float = 24 * 60 * 60) -> None:
        """Pass *sleeps* before stopping, each *step* seconds.

        The step is by default a day, which is past any interval, so that a
        sync is due each time.
        """
        self._now = 1_000_000.0
        self._sleeps_left = sleeps
        self._step = step
        self.on_sleep = None

    def time(self) -> float:
        return self._now

    def sleep(self, seconds: float) -> None:
        _ = seconds
        if self._sleeps_left == 0:
            raise KeyboardInterrupt
        self._sleeps_left -= 1
        self._now += self._step
        if self.on_sleep is not None:
            self.on_sleep(self._now)


def test_watch_goes_on_after_a_sync_goes_wrong(
    temp_home: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Whatever goes wrong in a sync is reported, and the next one is tried."""
    _ = temp_home
    monkeypatch.setattr("fogies.tools.claude_sync_watch.time", _Clock(sleeps=3))
    problems: list[Exception] = [
        # What claude-sync stopping is, and what its hooks can raise.
        ValueError("Not pushing, because the pull had conflicts."),
        PermissionError("The session is open in another program."),
        ConnectionError("No network."),
    ]
    syncs = 0

    def sync() -> None:
        nonlocal syncs
        syncs += 1
        if problems:
            raise problems.pop(0)

    with pytest.raises(KeyboardInterrupt):
        watch_and_sync(sync=sync)

    assert syncs == 4
    out = capsys.readouterr().out
    assert "Not pushing, because the pull had conflicts." in out
    assert "PermissionError: The session is open in another program." in out
    assert "ConnectionError: No network." in out
    assert "Synced." in out


def test_watch_tries_again_soon_after_a_sync_goes_wrong(
    temp_home: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed sync is not a sync: a change is still to be synced, and soon."""
    _ = temp_home
    start = 1_000_000.0

    def next_poll(at: float) -> float:
        """Return the first time at or after at that the watch looks, as it polls."""
        return start + math.ceil((at - start) / _POLL_SECONDS) * _POLL_SECONDS

    # The change is made at the first poll after the start, and the sync is due
    # at the first poll after it has been quiet for long enough. It fails, and is
    # tried again at the first poll after the retry delay, which is well before
    # the interval, so that is as far as it need go.
    change = start + _POLL_SECONDS
    failed = next_poll(change + _QUIET_SECONDS)
    retried = next_poll(failed + _RETRY_SECONDS)
    assert retried < start + _INTERVAL_SECONDS

    # One poll more than that, so the watch stops after the retry.
    clock = _Clock(
        sleeps=round((retried - start) / _POLL_SECONDS) + 1, step=_POLL_SECONDS
    )
    monkeypatch.setattr("fogies.tools.claude_sync_watch.time", clock)
    history = claude_directory() / "history.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    attempts: list[float] = []

    def change_after_the_first_sync(now: float) -> None:
        # Once, a moment after the first sync, which has nothing to sync.
        if len(attempts) == 1 and not history.exists():
            _ = history.write_text("changed", encoding="utf-8")
            os.utime(history, (now, now))

    clock.on_sleep = change_after_the_first_sync

    def sync() -> None:
        attempts.append(clock.time())
        # The second, of the change, fails, as with no network yet.
        if len(attempts) == 2:
            raise ConnectionError("No network.")

    with pytest.raises(KeyboardInterrupt):
        watch_and_sync(sync=sync)

    assert attempts == [start, failed, retried]


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
