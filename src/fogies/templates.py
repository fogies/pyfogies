"""Templates packaged with fogies, and the helper for auto-creating config files from them.

Templates themselves live under src/fogies/includes/templates/, kept
separate from source so bundled data and code aren't mixed in one
directory. Declared in pyproject.toml's [tool.poetry] include, same as
py.typed.
"""

import importlib.resources
import pathlib
from collections.abc import Callable


def ensure_from_template(
    *,
    path: pathlib.Path,
    template_factory: Callable[[], str],
    raise_if_file_not_found: bool = True,
) -> None:
    """Create path from template_factory() if it doesn't exist yet.

    template_factory is called only when path is missing, so callers can
    pass a factory wrapping a packaged-resource lookup (importlib.resources)
    without paying that cost when the file already exists.

    raise_if_file_not_found defaults to True: a template usually needs the
    reader to fill in real values (credentials, an API key), so first-time
    setup fails loudly with a message pointing at the file just created,
    instead of silently proceeding against a placeholder. Pass False for a
    template whose defaults are already usable as-is (e.g. an initially
    empty state-tracking file).
    """
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(template_factory(), encoding="utf-8")
    if raise_if_file_not_found:
        raise FileNotFoundError(
            "Expected file '{}' was not found, was created from template.".format(path)
        )


def _read_template_from_resources(name: str) -> str:
    return (
        importlib.resources.files("fogies.includes.templates")
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


def aws_toml_template_factory() -> str:
    return _read_template_from_resources("aws.toml.template")


def backend_status_toml_template_factory() -> str:
    return _read_template_from_resources("backend_status.toml.template")


def poetry_toml_template_factory() -> str:
    return _read_template_from_resources("poetry.toml.template")
