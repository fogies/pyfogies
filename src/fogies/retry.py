"""Retry policy for flaky one-off operations, built on tenacity.

Pass *log_path* to append a line for each retried failure. This is for
retries whose cause isn't already well understood and is worth investigating;
well-understood retries don't need it. Nothing is written, and no file is
created, unless a retry actually happens.
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
