"""Unit tests for fogies.ready_poll."""

import pytest

from fogies.ready_poll import ReadyPollTiming, ready_poll

_TIMING = ReadyPollTiming(timeout_seconds=10.0, poll_interval_seconds=0.1)


class _TestError(Exception):
    pass


class _OtherError(Exception):
    pass


def test_ready_poll_succeeds() -> None:
    calls = 0
    for attempt in ready_poll(exceptions=_TestError, timing=_TIMING):
        with attempt:
            calls += 1
            if calls < 5:
                raise _TestError("Not Yet")

    assert calls == 5


def test_ready_poll_ignores_other_exceptions() -> None:
    with pytest.raises(_OtherError):
        for attempt in ready_poll(exceptions=_TestError, timing=_TIMING):
            with attempt:
                raise _OtherError("Unrelated")
