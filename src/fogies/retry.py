"""Shared retry policies built on tenacity.

Call sites should use one of the named profiles below rather than inventing
timeout/interval/attempt values locally. Add a new profile here if a case
genuinely needs different numbers.

Pass *log_path* to a profile to append a line for each retried failure. This
is for retries whose cause isn't already well understood and is worth
investigating; well-understood retries (e.g. polling for a resource to come
up) don't need it. Nothing is written, and no file is created, unless a
retry actually happens.
"""

import pathlib
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

import tenacity

_T = TypeVar("_T")


def _log_retry(log_path: pathlib.Path) -> Callable[[tenacity.RetryCallState], None]:
    def log_it(retry_state: tenacity.RetryCallState) -> None:
        outcome = retry_state.outcome
        assert outcome is not None and outcome.failed
        exception = outcome.exception()
        assert exception is not None
        line = "{} attempt {} raised {}: {}\n".format(
            datetime.now().isoformat(timespec="seconds"),
            retry_state.attempt_number,
            type(exception).__name__,
            exception,
        )
        with log_path.open("a", encoding="utf-8") as f:
            _ = f.write(line)

    return log_it


def readiness_poll(
    *,
    exceptions: type[BaseException] | tuple[type[BaseException], ...],
    timeout: float,
    poll_interval: float,
    reraise: bool = True,
) -> tenacity.Retrying:
    """Retry policy for polling until a resource becomes ready or *timeout* elapses.

    Retries only on *exceptions*; any other exception propagates immediately.
    On giving up, re-raises the last *exceptions* instance unless *reraise* is
    False, in which case a `tenacity.RetryError` is raised instead.
    """
    return tenacity.Retrying(
        retry=tenacity.retry_if_exception_type(exceptions),
        wait=tenacity.wait_fixed(poll_interval),
        stop=tenacity.stop_after_delay(timeout),
        reraise=reraise,
    )


def readiness_poll_short(
    *,
    exceptions: type[BaseException] | tuple[type[BaseException], ...],
    reraise: bool = True,
) -> tenacity.Retrying:
    """Readiness poll profile for something expected ready within seconds."""
    return readiness_poll(
        exceptions=exceptions,
        timeout=10.0,
        poll_interval=0.1,
        reraise=reraise,
    )


def readiness_poll_long(
    *,
    exceptions: type[BaseException] | tuple[type[BaseException], ...],
    reraise: bool = True,
) -> tenacity.Retrying:
    """Readiness poll profile for something that can take minutes to become ready."""
    return readiness_poll(
        exceptions=exceptions,
        timeout=300.0,
        poll_interval=5.0,
        reraise=reraise,
    )


def retry_transient(
    *,
    exceptions: type[BaseException] | tuple[type[BaseException], ...],
    log_path: pathlib.Path | None = None,
) -> Callable[[Callable[[], _T]], Callable[[], _T]]:
    """Retry profile for a flaky one-off operation, with no backoff."""
    return tenacity.retry(
        retry=tenacity.retry_if_exception_type(exceptions),
        stop=tenacity.stop_after_attempt(5),
        reraise=True,
        before_sleep=_log_retry(log_path) if log_path is not None else None,
    )
