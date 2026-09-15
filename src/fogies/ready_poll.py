"""Readiness-polling profiles built on tenacity.

Call sites should use one of the named profiles below rather than inventing
timing/exception values locally. Add a new profile here if a case genuinely
needs different numbers.
"""

import dataclasses
import socket

import requests
import tenacity

# Exceptions that mean DNS resolution hasn't propagated yet.
READY_POLL_EXCEPTIONS_DNS: tuple[type[BaseException], ...] = (socket.gaierror,)

# Exceptions that mean an HTTP endpoint is not yet ready.
READY_POLL_EXCEPTIONS_HTTP: tuple[type[BaseException], ...] = (
    requests.exceptions.ConnectionError,
    requests.exceptions.HTTPError,
    requests.exceptions.SSLError,
    requests.exceptions.Timeout,
    TimeoutError,
)


@dataclasses.dataclass(frozen=True, slots=True)
class ReadyPollTiming:
    """Timeout and poll-interval pair for ready_poll, both in seconds."""

    timeout_seconds: float
    poll_interval_seconds: float


# Profile for something that can take minutes to become ready.
READY_POLL_TIMING_LONG = ReadyPollTiming(
    timeout_seconds=300.0, poll_interval_seconds=5.0
)

# Profile for something expected ready within seconds.
READY_POLL_TIMING_SHORT = ReadyPollTiming(
    timeout_seconds=10.0, poll_interval_seconds=0.5
)


def ready_poll(
    *,
    exceptions: type[BaseException] | tuple[type[BaseException], ...],
    timing: ReadyPollTiming,
    reraise: bool = True,
) -> tenacity.Retrying:
    """Retry policy for polling until a resource becomes ready or *timing.timeout_seconds* elapses.

    Retries only on *exceptions*; any other exception propagates immediately.
    On giving up, re-raises the last *exceptions* instance unless *reraise* is
    False, in which case a `tenacity.RetryError` is raised instead.
    """
    return tenacity.Retrying(
        retry=tenacity.retry_if_exception_type(exceptions),
        wait=tenacity.wait_fixed(timing.poll_interval_seconds),
        stop=tenacity.stop_after_delay(timing.timeout_seconds),
        reraise=reraise,
    )
