"""Tests for fogies.tools.environ."""

import os

import pytest

from fogies.tools.environ import environ


def test_environ_sets_and_restores_new_variable() -> None:
    """environ sets a new variable and removes it on exit."""
    name = "PYFOGIES_TEST_ENVIRON_NEW"
    if name in os.environ:
        del os.environ[name]

    with environ({name: "value"}):
        assert os.environ.get(name) == "value"

    assert name not in os.environ


def test_environ_raises_when_exists() -> None:
    """environ raises ValueError when variable exists and raise_if_exists is True."""
    name = "PYFOGIES_TEST_ENVIRON_EXISTS"
    os.environ[name] = "exists"

    try:
        with pytest.raises(ValueError):
            with environ({name: "new"}):
                pass
    finally:
        if name in os.environ:
            del os.environ[name]


def test_environ_allows_exists_when_flag_false() -> None:
    """environ allows overriding existing variable when raise_if_exists is False."""
    name = "PYFOGIES_TEST_ENVIRON_ALLOW_EXISTS"
    original = os.environ.get(name)
    os.environ[name] = "exists"

    try:
        with environ(
            {
                name: "new",
            },
            raise_if_exists=False,
        ):
            assert os.environ.get(name) == "new"

        assert os.environ.get(name) == "exists"
    finally:
        if original is None:
            if name in os.environ:
                del os.environ[name]
        else:
            os.environ[name] = original


def test_environ_raises_when_changed() -> None:
    """environ raises RuntimeError when variable value is changed inside context."""
    name = "PYFOGIES_TEST_ENVIRON_CHANGED"
    if name in os.environ:
        del os.environ[name]

    with pytest.raises(RuntimeError):
        with environ({name: "initial"}):
            os.environ[name] = "modified"

    assert name not in os.environ


def test_environ_allows_changed_when_flag_false() -> None:
    """environ does not raise when raise_if_changed is False."""
    name = "PYFOGIES_TEST_ENVIRON_CHANGED_DISABLED"
    if name in os.environ:
        del os.environ[name]

    with environ(
        {
            name: "initial",
        },
        raise_if_changed=False,
    ):
        os.environ[name] = "modified"

    assert name not in os.environ
