"""Test running a task in a new terminal."""

import json
import platform
import subprocess
import sys

import pytest
from invoke.context import Context

from fogies.tasks.terminal import (
    _windows_arguments,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tasks.terminal import (
    spawn_new_terminal,
)


def test_spawn_new_terminal_spawns_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A command spawns one terminal, which does not spawn another for it."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(sys, "argv", ["invoke.exe", "claude-sync.sync", "--watch"])
    spawned: list[dict[str, str]] = []

    def run(command: str, *, env: dict[str, str], disown: bool) -> None:
        _ = (command, disown)
        spawned.append(env)

    context = Context()
    monkeypatch.setattr(context, "run", run)

    # In the original terminal.
    assert spawn_new_terminal(context) is False
    assert len(spawned) == 1

    # In the terminal that was spawned, which has the environment it was given.
    for name, value in spawned[0].items():
        monkeypatch.setenv(name, value)
    assert spawn_new_terminal(context) is True
    assert len(spawned) == 1

    # Another command in that terminal can spawn a terminal of its own.
    monkeypatch.setattr(sys, "argv", ["invoke.exe", "other"])
    assert spawn_new_terminal(context) is False
    assert len(spawned) == 2


@pytest.mark.skipif(
    sys.platform != "win32", reason="Quoting for cmd, which is Windows."
)
def test_windows_arguments_reach_the_command_as_they_were() -> None:
    """What `cmd` would otherwise read in an argument, or split it by, is not."""
    arguments = [
        "a b",
        "x&y",
        "x|y",
        "x<y>z",
        "x^y",
        'say "hi"',
        "",
        # A backslash before the quote that ends it.
        "C:\\Program Files\\",
        'a\\"b\\"c',
    ]
    command_line = [
        sys.executable,
        "-c",
        "import json, sys; print(json.dumps(sys.argv[1:]))",
        *arguments,
    ]

    # With `cmd /c`, which unwraps what follows as `cmd /k` does, in a window.
    result = subprocess.run(
        "cmd /c {}".format(_windows_arguments(command_line)),
        shell=True,
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(result.stdout) == arguments
