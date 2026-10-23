"""Test running a task in a new terminal."""

import sys

import pytest
from invoke.context import Context

from fogies.tasks.terminal import (
    _invoke_command_line,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tasks.terminal import (
    _is_new_terminal,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tasks.terminal import (
    _windows_command,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tasks.terminal import (
    spawn_new_terminal,
)


def test_invoke_command_line(monkeypatch: pytest.MonkeyPatch) -> None:
    """The command that is run again is the current one, with its arguments."""
    monkeypatch.setattr(sys, "argv", ["invoke.exe", "claude-sync.sync", "--watch"])

    # With the interpreter that is running, not whatever is on the PATH.
    assert _invoke_command_line() == [
        sys.executable,
        "-m",
        "invoke",
        "claude-sync.sync",
        "--watch",
    ]


def test_is_new_terminal_for_the_same_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """A terminal that was spawned does not spawn another for the same command."""
    command_line = ["python", "-m", "invoke", "claude-sync.sync", "--watch"]
    monkeypatch.setenv("INVOKE_SPAWN_NEW_TERMINAL", " ".join(command_line))

    assert _is_new_terminal(command_line)
    # Another command in that terminal can spawn a terminal of its own.
    assert not _is_new_terminal(["python", "-m", "invoke", "other"])


def test_is_new_terminal_when_not_spawned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INVOKE_SPAWN_NEW_TERMINAL", raising=False)

    assert not _is_new_terminal(["python", "-m", "invoke", "task"])


def test_spawn_new_terminal_in_a_new_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """It does not spawn from a terminal that was spawned for this command."""
    monkeypatch.setattr(sys, "argv", ["invoke.exe", "claude-sync.sync", "--watch"])
    monkeypatch.setenv(
        "INVOKE_SPAWN_NEW_TERMINAL",
        " ".join([sys.executable, "-m", "invoke", "claude-sync.sync", "--watch"]),
    )

    assert spawn_new_terminal(Context()) is True


def test_windows_command() -> None:
    """Every argument is quoted, for cmd, and the whole is for `cmd /k` to unwrap."""
    command = _windows_command(
        ["C:\\Program Files\\Python\\python.exe", "-m", "invoke", "a b", "x&y"]
    )

    assert command == (
        'start cmd /k ^""C:\\Program Files\\Python\\python.exe" "-m" "invoke"'
        ' "a b" "x&y"^"'
    )
