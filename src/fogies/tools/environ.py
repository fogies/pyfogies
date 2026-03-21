"""Context managers for temporary environment variable overrides."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Mapping


class _EnvironContext:
    """Context manager for environment variable overrides."""

    def __init__(
        self,
        variables: Mapping[str, str],
        *,
        raise_if_exists: bool,
        raise_if_changed: bool,
    ) -> None:
        self._variables: dict[str, str] = {
            name: str(value) for name, value in variables.items()
        }
        self._raise_if_exists: bool = raise_if_exists
        self._raise_if_changed: bool = raise_if_changed
        self._original_variables: dict[str, str | None] = {}
        self._applied_variables: list[str] = []

    def _restore_originals(self) -> None:
        """Restore each applied variable to its original value or remove it."""
        for name in reversed(self._applied_variables):
            original = self._original_variables.get(name)
            if original is None:
                if name in os.environ:
                    del os.environ[name]
            else:
                os.environ[name] = original

    def __enter__(self) -> None:
        try:
            for name, value in self._variables.items():
                existing = os.environ.get(name)
                if existing is not None and self._raise_if_exists:
                    raise ValueError(
                        "Environment variable '{}' already exists".format(name)
                    )

                self._original_variables[name] = existing
                os.environ[name] = value
                self._applied_variables.append(name)
        except Exception:
            # Roll back any changes made before the failure.
            self._restore_originals()
            raise
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        exc_tb: object | None,
    ) -> bool:
        error: RuntimeError | None = None

        # Enforce raise_if_changed only when the body exited normally.
        if exc_type is None and self._raise_if_changed:
            for name in self._applied_variables:
                expected = self._variables[name]
                current = os.environ.get(name)
                if current != expected:
                    error = RuntimeError(
                        "Environment variable '{}' was modified while context manager was active".format(
                            name
                        )
                    )
                    break

        # Always restore original values.
        self._restore_originals()

        if error is not None:
            raise error

        return False


def environ(
    variables: Mapping[str, str],
    *,
    raise_if_exists: bool = True,
    raise_if_changed: bool = True,
) -> contextlib.AbstractContextManager[None]:
    """Return a context manager that applies the given environment overrides.

    The *variables* mapping provides environment variable names and string values
    to assign for the duration of the context.

    For each variable:
    - If raise_if_exists is True (default) and the variable already exists,
      raises ValueError and leaves the environment unchanged.
    - On normal exit, if raise_if_changed is True (default) and the value in
      the environment differs from the value set by this context manager,
      raises RuntimeError.
    """
    return _EnvironContext(
        variables=variables,
        raise_if_exists=raise_if_exists,
        raise_if_changed=raise_if_changed,
    )
