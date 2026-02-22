import dataclasses
import pathlib
import subprocess
from typing import assert_never, cast

from invoke.context import Context
from invoke.runners import Result


@dataclasses.dataclass
class ContextCommandParams:
    """Params for execution via invoke context.run()."""

    context: Context


@dataclasses.dataclass
class SubprocessCommandParams:
    """Params for execution via subprocess.run()."""

    capture_output: bool = False


CommandParams = ContextCommandParams | SubprocessCommandParams


def command_run(
    *,
    command: pathlib.Path,
    command_params: CommandParams,
    args: list[str] | None = None,
    cwd: pathlib.Path | None = None,
) -> subprocess.CompletedProcess[str] | Result:
    """Run a command via context.run() or subprocess.run()."""
    args_combined = [str(command)] + (args or [])
    if isinstance(command_params, ContextCommandParams):
        if cwd is not None:
            context_cd = (
                command_params.context.cd(  # pyright: ignore[reportUnknownMemberType]
                    str(cwd)
                )
            )
            with context_cd:
                result = command_params.context.run(" ".join(args_combined))
        else:
            result = command_params.context.run(" ".join(args_combined))

        # invoke's context.run() returns None when run with disown=True.
        # Ensure future revisions to this code never introduce that parameter.
        return cast(Result, result)
    elif isinstance(
        command_params, SubprocessCommandParams
    ):  # pyright: ignore[reportUnnecessaryIsInstance]
        return subprocess.run(
            args_combined,
            capture_output=command_params.capture_output,
            text=True if command_params.capture_output else None,
            cwd=cwd,
        )
    else:
        assert_never(command_params)
