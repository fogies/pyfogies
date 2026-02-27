import dataclasses
import pathlib
from typing import cast

from invoke.context import Context
from invoke.runners import Result


@dataclasses.dataclass
class CommandParams:
    """Params for execution via invoke."""

    cwd: pathlib.Path | None = None


def command_run(
    *,
    context: Context | None = None,
    command: pathlib.Path,
    command_params: CommandParams | None = None,
    args: list[str] | None = None,
) -> Result:
    """Run a command via invoke run().

    If *context* is provided, use context.run(). Otherwise create a new
    Context and run the command there.
    """
    command_params = command_params or CommandParams()
    context = context or Context()

    args_combined = [str(command)] + (args or [])
    command_str = " ".join(args_combined)

    if command_params.cwd is not None:
        context_cd = context.cd(str(command_params.cwd))  # pyright: ignore[reportUnknownMemberType]
        with context_cd:
            result = context.run(command_str)
    else:
        result = context.run(command_str)

    # invoke's Context.run() returns None when run with disown=True.
    # Ensure future revisions to this code never introduce that parameter.
    return cast(Result, result)
