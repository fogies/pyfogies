"""Keeping claude-sync in sync by watching, and syncing when it is time to.

A sync is a pull and a push, so it is not done on every change. Sessions are
files that are rewritten as they are used, and the bucket keeps a version of
each file that a push replaces. So a sync is done after local changes stop for a
while, and otherwise on a slower interval, which also brings in what other
machines have pushed.
"""

import datetime
import pathlib
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager

from filelock import FileLock, Timeout
from invoke.exceptions import Failure

from fogies.tools.claude_sync import (
    SESSIONS_PATHS,
    claude_directory,
    claude_sync_files_directory,
)

# How often to look for changes, in seconds.
_POLL_SECONDS = 30

# How long local changes have to have stopped for before a sync, in seconds.
_QUIET_SECONDS = 10 * 60

# How long between syncs, however quiet it is, in seconds.
_INTERVAL_SECONDS = 60 * 60

# How long after a sync that failed before trying again, in seconds.
_RETRY_SECONDS = 5 * 60


def newest_change(*, directory: pathlib.Path) -> float | None:
    """Return when a polled file in directory last changed, or None if none exist."""
    newest: float | None = None
    # Only what the sessions scope syncs, whatever the scope is. What else a
    # full scope syncs (e.g., plugins) is picked up on the interval, instead of
    # being polled for.
    for name in SESSIONS_PATHS:
        path = directory / name
        paths = [path, *path.rglob("*")] if path.is_dir() else [path]
        for candidate in paths:
            try:
                modified = candidate.stat().st_mtime
            except OSError:
                # Gone since it was listed, or being replaced.
                continue
            if newest is None or modified > newest:
                newest = modified
    return newest


def sync_due(
    *,
    now: float,
    newest_change: float | None,
    synced_change: float | None,
    last_sync: float,
    last_attempt: float,
    quiet_seconds: float,
    interval_seconds: float,
    retry_seconds: float,
) -> bool:
    """Return whether it is time to sync.

    That is when the interval has passed since the last sync, or when there
    has been a change since synced_change, the newest change as of the end of
    the last sync, that has been quiet for quiet_seconds. A sync writes files
    itself (e.g., the history it rebuilds), which are not changes to sync again.

    Not within retry_seconds of last_attempt, though, as a sync that failed (e.g.,
    no network yet) is not a sync, and so is tried again soon, not at the
    interval, but not as often as it is polled for.
    """
    if now - last_attempt < retry_seconds:
        return False
    if now - last_sync >= interval_seconds:
        return True
    return (
        newest_change is not None
        and (synced_change is None or newest_change > synced_change)
        and now - newest_change >= quiet_seconds
    )


@contextmanager
def _watch_lock() -> Generator[None]:
    """Hold this machine's lock on watching, which only one watch can have.

    The operating system releases it when the process ends, however it ends, so
    one that is left behind is not a watch that is running. On Windows that is
    a moment after, so a watch started at once after another is killed may be
    refused, and can be started again. Raises ValueError if another watch has it.
    """
    directory = claude_sync_files_directory()
    directory.mkdir(parents=True, exist_ok=True)
    lock = FileLock(directory / "watch.lock", timeout=0)
    try:
        _ = lock.acquire()
    except Timeout as exc:
        raise ValueError(
            "claude-sync is already being watched, in another terminal."
        ) from exc
    try:
        yield
    finally:
        lock.release()


def is_watching() -> bool:
    """Return whether a watch is running on this machine."""
    try:
        with _watch_lock():
            return False
    except ValueError:
        return True


def _say(message: str) -> None:
    print("{}  {}".format(datetime.datetime.now().strftime("%H:%M:%S"), message))


def watch_and_sync(*, sync: Callable[[], None]) -> None:
    """Call sync whenever it is time to, until interrupted.

    A sync that stops because of an error, such as a ValueError (e.g.,
    conflicts), a failed command, or a failure in what it does after the pull
    (e.g., no network), is reported, and tried again after a few minutes, until
    one finishes. Raises ValueError, without syncing, if another watch is
    running, as two would sync over each other.
    """
    directory = claude_directory()

    with _watch_lock():
        last_sync = 0.0
        last_attempt = 0.0
        synced_change: float | None = None
        _say("Watching and syncing. Stop with Ctrl+C.")
        while True:
            if sync_due(
                now=time.time(),
                newest_change=newest_change(directory=directory),
                synced_change=synced_change,
                last_sync=last_sync,
                last_attempt=last_attempt,
                quiet_seconds=_QUIET_SECONDS,
                interval_seconds=_INTERVAL_SECONDS,
                retry_seconds=_RETRY_SECONDS,
            ):
                last_attempt = time.time()
                try:
                    sync()
                except (ValueError, Failure) as exc:
                    _say(str(exc))
                except Exception as exc:
                    # Nothing that goes wrong in a sync (e.g., the network
                    # being down, or a session file being open) is a reason
                    # for an unattended watch to stop.
                    _say("{}: {}".format(type(exc).__name__, exc))
                else:
                    _say("Synced.")
                    last_sync = last_attempt
                    # What the sync wrote is not a change to sync again. A
                    # change made while it ran is not either, which the
                    # interval brings in. After a failed sync it is left, as
                    # what was to be synced still is.
                    synced_change = newest_change(directory=directory)
            time.sleep(_POLL_SECONDS)
