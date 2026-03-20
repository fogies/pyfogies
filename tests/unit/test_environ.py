"""Tests for fogies.tools.environ."""

import os

import pytest

from fogies.tools.environ import environ


def test_environ_sets_and_restores_new_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """environ sets a new variable and removes it on exit."""
    name = "PYFOGIES_TEST_ENVIRON_NEW"
    monkeypatch.delenv(name, raising=False)

    with environ({name: "value"}):
        assert os.environ.get(name) == "value"

    assert name not in os.environ


def test_environ_raises_when_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """environ raises ValueError when variable exists and raise_if_exists is True."""
    name = "PYFOGIES_TEST_ENVIRON_EXISTS"
    monkeypatch.setenv(name, "exists")

    with pytest.raises(ValueError):
        with environ({name: "new"}):
            pass


def test_environ_allows_exists_when_flag_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """environ allows overriding existing variable when raise_if_exists is False."""
    name = "PYFOGIES_TEST_ENVIRON_ALLOW_EXISTS"
    monkeypatch.setenv(name, "exists")

    with environ(
        {
            name: "new",
        },
        raise_if_exists=False,
    ):
        assert os.environ.get(name) == "new"

    # Original value is restored after context exit.
    assert os.environ.get(name) == "exists"


def test_environ_raises_when_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    """environ raises RuntimeError when variable value is changed inside context."""
    name = "PYFOGIES_TEST_ENVIRON_CHANGED"
    monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError):
        with environ({name: "initial"}):
            os.environ[name] = "modified"

    assert name not in os.environ


def test_environ_allows_changed_when_flag_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """environ does not raise when raise_if_changed is False."""
    name = "PYFOGIES_TEST_ENVIRON_CHANGED_DISABLED"
    monkeypatch.delenv(name, raising=False)

    with environ(
        {
            name: "initial",
        },
        raise_if_changed=False,
    ):
        os.environ[name] = "modified"

    assert name not in os.environ
