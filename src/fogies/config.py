"""Loading config files, in one place.

A config file is TOML at a path that a project chooses, and is loaded into a
pydantic model. The file at that path may instead be a redirect, so that
projects can share one config rather than each repeating it:

    redirect = "../shared/aws.toml"

The path is relative to the file that has the redirect, and the file has
nothing else in it. Anything that is common to loading every config, such as
redirects, belongs here rather than in each loader.
"""

import pathlib
import tomllib
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from fogies.templates import ensure_from_template

ConfigModel = TypeVar("ConfigModel", bound=BaseModel)

_REDIRECT_KEY = "redirect"


def _read_toml(*, path: pathlib.Path) -> dict[str, object]:
    with path.open("rb") as f:
        return tomllib.load(f)


def _redirect_target(
    *, path: pathlib.Path, data: dict[str, object]
) -> pathlib.Path | None:
    """Return where data, read from path, redirects to, or None if it doesn't."""
    if _REDIRECT_KEY not in data:
        return None
    target = data[_REDIRECT_KEY]
    if len(data) != 1 or not isinstance(target, str):
        raise ValueError(
            "'{}' has a '{}', so it must contain only that, as a path.".format(
                path, _REDIRECT_KEY
            )
        )
    return path.parent / target


def resolve_config_path(*, path: pathlib.Path) -> pathlib.Path:
    """Return the file that holds the config at path.

    That is path itself, or the file that it redirects to. Use this to write to
    a config, so that the write goes to the shared file and not the redirect.
    """
    if not path.exists():
        return path

    target = _redirect_target(path=path, data=_read_toml(path=path))
    if target is None:
        return path

    if not target.exists():
        raise FileNotFoundError(
            "'{}' redirects to '{}', which was not found.".format(path, target)
        )
    if _redirect_target(path=target, data=_read_toml(path=target)) is not None:
        raise ValueError(
            "'{}' redirects to '{}', which is itself a redirect.".format(path, target)
        )
    return target


def load_config(
    *,
    path: pathlib.Path,
    model: type[ConfigModel],
    template_factory: Callable[[], str],
) -> ConfigModel:
    """Load the config at path as a model.

    If path doesn't exist, it is created from template_factory and
    FileNotFoundError is raised, so that it is filled in before it is used; see
    ensure_from_template(). If path redirects, the config is the file it
    redirects to. Raises a pydantic ValidationError if the config does not match
    model.
    """
    ensure_from_template(path=path, template_factory=template_factory)
    return model.model_validate(_read_toml(path=resolve_config_path(path=path)))
