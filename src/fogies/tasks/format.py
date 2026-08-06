"""
Tasks for applying code formatting.
"""

import pathlib
from typing import Callable, cast

from invoke.context import Context
from invoke.tasks import Task, task

from fogies.tools.command import CommandParams
from fogies.tools.terraform import terraform


def get_task_format(
    *,
    fmt_black: bool = False,
    fmt_isort: bool = False,
    fmt_terraform: bool = False,
    terraform_binary_cache_path: pathlib.Path | None = None,
) -> Task[Callable[[Context], None]]:
    if fmt_terraform and terraform_binary_cache_path is None:
        raise ValueError(
            "terraform_binary_cache_path is required when fmt_terraform is set"
        )
    if not (fmt_black or fmt_isort or fmt_terraform):
        raise ValueError(
            "At least one fmt flag must be set."
        )

    @task(name="format")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_format(context: Context) -> None:
        """
        Apply code formatting.
        """
        # isort before black: black should see the post-sort import layout.
        if fmt_isort:
            _ = context.run(
                command=" ".join(
                    [
                        "isort",
                        ".",
                    ]
                ),
                echo=True,
            )

        if fmt_black:
            _ = context.run(
                command=" ".join(
                    [
                        "black",
                        ".",
                    ]
                ),
                echo=True,
            )

        if fmt_terraform:
            assert terraform_binary_cache_path is not None
            with terraform(binary_cache_path=terraform_binary_cache_path) as tf:
                _ = tf.format(
                    command_params=CommandParams(context=context),
                    path=pathlib.Path("."),
                )

    return cast(Task[Callable[[Context], None]], task_format)
