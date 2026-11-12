"""Helper for running a task in a new terminal."""

import os
import pathlib
import platform
import shlex
import stat
import sys

from invoke.context import Context

# Set in a new terminal to the command it runs, so that it can tell it is one.
_NEW_TERMINAL_VARIABLE = "INVOKE_SPAWN_NEW_TERMINAL"

# Restored in a new terminal on macOS, which does not inherit them. Based on a
# manual inspection of what configures the virtual environment.
_MACOS_RESTORED_VARIABLES = [
    "PATH",
    "PIPENV_ACTIVE",
    "PIP_DISABLE_PIP_VERSION_CHECK",
    "PIP_PYTHON_PATH",
    "PS1",
    "PYTHONDONTWRITEBYTECODE",
    "VIRTUAL_ENV",
]


def _invoke_command_line() -> list[str]:
    """Return the command that runs the current invoke command again.

    It runs with the interpreter that is running now, which does not depend on
    what is on the PATH of a new terminal.
    """
    return [sys.executable, "-m", "invoke"] + sys.argv[1:]


def _is_new_terminal(command_line: list[str]) -> bool:
    """Return whether this is a new terminal that was spawned to run command_line.

    Only for that command, so that another command run in the same terminal
    can spawn a terminal of its own.
    """
    return os.environ.get(_NEW_TERMINAL_VARIABLE) == " ".join(command_line)


def _cmd_quote(argument: str) -> str:
    """Return argument quoted for `cmd`, which otherwise reads & | < > and ^ in it.

    A % is still read by `cmd` as the start of an environment variable.
    """
    return '"{}"'.format(argument.replace('"', '\\"'))


def _windows_command(command_line: list[str]) -> str:
    """Return the command that opens a new window running command_line.

    The new `cmd /k` removes the first and last quote of what follows it when
    that starts with a quote, so the whole is wrapped in a pair for it to
    remove, which leaves each argument quoted, including a path to the
    interpreter that has spaces in it. The `cmd` that runs this line first
    reads a quote as starting or ending what is protected from & and |, so the
    pair is escaped with a caret, for it to pass on without counting it.
    """
    return 'start cmd /k ^"{}^"'.format(
        " ".join(_cmd_quote(argument) for argument in command_line)
    )


def _export(name: str, value: str) -> str:
    """Return a shell command that exports an environment variable."""
    return "export {}={}".format(name, shlex.quote(value))


def spawn_new_terminal(context: Context) -> bool:
    """Spawn a new terminal to run the current command.

    Returns True in the new terminal, False in the original terminal. A task
    that should continue only in the new terminal starts with:

        if not spawn_new_terminal(context):
            return

    Whether this is the new terminal is flagged with an environment variable,
    so a new terminal does not spawn further terminals for the same command.
    """
    command_line = _invoke_command_line()
    if _is_new_terminal(command_line):
        return True

    flag = " ".join(command_line)
    platform_current = platform.system()

    if platform_current.casefold() == "windows":
        # `start` opens a new window with `cmd`, whose `/k` keeps it open after
        # the command completes (e.g., to view its output). It starts in the
        # same directory, with the same environment variables.
        _ = context.run(
            command=_windows_command(command_line),
            env={_NEW_TERMINAL_VARIABLE: flag},
            # The task proceeds in the new terminal.
            disown=True,
        )
    elif platform_current.casefold() == "darwin":
        # Write a command file, make it executable, and `open` it in `Terminal`.
        # The new terminal starts in the home directory, and does not inherit
        # environment variables.
        path_cwd = pathlib.Path.cwd()
        path_command = path_cwd / "INVOKE_SPAWN_NEW_TERMINAL.command"
        lines = [
            "# Set what the new terminal checks to know it is one",
            _export(_NEW_TERMINAL_VARIABLE, flag),
            "",
            "# Restore the working directory",
            'cd "{}"'.format(path_cwd),
            "",
            "# Restore environment variables that configure the virtual environment",
        ]
        for name in _MACOS_RESTORED_VARIABLES:
            value = os.getenv(name)
            if value is not None:
                lines.append(_export(name, value))
        lines += [
            "",
            "# Delete this command file",
            'rm -f "{}"'.format(path_command),
            "",
            "# Finally, run the command in the new terminal",
            " ".join('"{}"'.format(argument) for argument in command_line),
        ]
        _ = path_command.write_text(
            "".join(line + "\n" for line in lines), encoding="utf-8"
        )
        path_command.chmod(path_command.stat().st_mode | stat.S_IXUSR)

        _ = context.run(
            command='open -a Terminal "{}"'.format(path_command),
            disown=True,
        )
    else:
        raise ValueError(
            'Unsupported platform in spawn_new_terminal: "{}"'.format(platform_current)
        )

    return False
