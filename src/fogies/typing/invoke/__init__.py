"""
Type-preserving wrapper for invoke's task decorator.

This module provides a properly typed wrapper around invoke's task decorator
that preserves function type information for type checkers.
"""

from typing import Callable, ParamSpec, TypeVar, cast

from invoke.tasks import task as _invoke_task  # pyright: ignore[reportUnknownVariableType]

P = ParamSpec("P")
R = TypeVar("R")


def task(*args: object, **kwargs: object) -> Callable[[Callable[P, R]], Callable[P, R]] | Callable[P, R]:
    """
    Type-preserving wrapper for invoke's task decorator.

    This function preserves the decorated function's type signature for
    type checkers while delegating to invoke's actual task decorator.
    """
    result = cast(
        Callable[[Callable[P, R]], Callable[P, R]] | Callable[P, R],
        _invoke_task(*args, **kwargs),
    )
    return result

