import dataclasses
import os
import pathlib
from typing import cast

from invoke.context import Context
from invoke.runners import Result


@dataclasses.dataclass(frozen=True, slots=True)
class CommandParams:
    """Params for execution via invoke."""

    context: Context | None = None
    cwd: pathlib.Path | None = None
    in_stream: bool = True

    def require_cwd(self, path: pathlib.Path) -> "CommandParams":
        """Ensure cwd is set to *path*; return updated params or raise if conflicting."""
        if self.cwd is None:
            return dataclasses.replace(self, cwd=path)
        if self.cwd == path:
            return self
        raise ValueError(
            "CommandParams requires cwd '{}' but already has '{}'".format(
                path,
                self.cwd,
            )
        )


def _resolve_command(
    command: pathlib.Path,
    cwd: pathlib.Path | None,
) -> str:
    """Return the command string to pass to the shell.

    When *cwd* is set and *command* resolves to an existing file (a specific
    binary), returns a path relative to *cwd*. Otherwise returns the command as
    given so a name like \"bash\" is left for PATH (e.g. shutil.which).
    """
    if cwd is not None:
        resolved = command.resolve()
        if resolved.exists():
            return os.path.relpath(resolved, cwd.resolve())
    return str(command)


def command_run(
    *,
    command: pathlib.Path,
    command_params: CommandParams | None = None,
    args: list[str] | None = None,
) -> Result:
    """Run a command via invoke run().

    If *context* is provided, use context.run(). Otherwise create a new
    Context and run the command there.
    """
    command_params = command_params or CommandParams()
    context = command_params.context or Context()

    resolved_command = _resolve_command(command, command_params.cwd)
    args_combined = [resolved_command] + (args or [])
    command_str = " ".join(args_combined)

    if command_params.cwd is not None:
        context_cd = context.cd(  # pyright: ignore[reportUnknownMemberType]
            str(command_params.cwd)
        )
        with context_cd:
            result = context.run(command_str, in_stream=command_params.in_stream)
    else:
        result = context.run(command_str, in_stream=command_params.in_stream)

    # invoke's Context.run() returns None when run with disown=True.
    # Ensure future revisions to this code never introduce that parameter.
    return cast(Result, result)
