"""Unit tests for fogies.retry."""

import pathlib
import pytest

from fogies.retry import readiness_poll, retry_transient


class _TestError(Exception):
    pass


class _OtherError(Exception):
    pass


def test_readiness_poll_succeeds() -> None:
    calls = 0
    for attempt in readiness_poll(exceptions=_TestError, timeout=10.0, poll_interval=0.1):
        with attempt:
            calls += 1
            if calls < 5:
                raise _TestError("Not Yet")
    
    assert calls == 5


def test_readiness_poll_ignores_other_exceptions() -> None:
    with pytest.raises(_OtherError):
        for attempt in readiness_poll(exceptions=_TestError, timeout=10.0, poll_interval=0.1):
            with attempt:
                raise _OtherError("Unrelated")


def test_retry_transient_succeeds() -> None:
    calls = 0

    @retry_transient(exceptions=_TestError)
    def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise _TestError("Transient")
        return "Success"

    assert flaky() == "Success"
    assert calls == 3


def test_retry_transient_reraises() -> None:
    calls = 0

    @retry_transient(exceptions=_TestError)
    def always_fails() -> None:
        nonlocal calls
        calls += 1
        raise _TestError("Always")

    with pytest.raises(_TestError, match="Always"):
        always_fails()
    
    # Current implementation retries 5 times by default.
    assert calls == 5


def test_retry_transient_ignores_other_exceptions() -> None:
    @retry_transient(exceptions=_TestError)
    def wrong_error() -> None:
        raise _OtherError("Wrong")

    with pytest.raises(_OtherError):
        wrong_error()


def test_retry_transient_log_path(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "retry.log"
    calls = 0

    @retry_transient(exceptions=_TestError, log_path=log_path)
    def sometimes_fails() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise _TestError("Retry")
        return "Success"

    _ = sometimes_fails()

    assert log_path.exists()
    assert "Retry" in log_path.read_text(encoding="utf-8")


def test_retry_transient_no_log_without_retry(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "retry.log"

    @retry_transient(exceptions=_TestError, log_path=log_path)
    def succeeds() -> str:
        return "Success"

    _ = succeeds()
    assert not log_path.exists()
