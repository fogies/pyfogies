"""Unit tests for fogies.templates."""

import pathlib
from collections.abc import Callable

import pytest

from fogies.templates import (
    aws_toml_template_factory,
    backend_status_toml_template_factory,
    ensure_from_template,
    poetry_toml_template_factory,
)


def test_ensure_from_template_creates_missing_file(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "nested" / "config.toml"

    ensure_from_template(path=path, template_factory=lambda: "content")

    assert path.read_text(encoding="utf-8") == "content"


def test_ensure_from_template_leaves_existing_file_untouched(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text("original", encoding="utf-8")

    def _fail() -> str:
        raise AssertionError(
            "template_factory() should not be called when path already exists"
        )

    ensure_from_template(path=path, template_factory=_fail)

    assert path.read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize(
    "template_factory",
    [
        aws_toml_template_factory,
        backend_status_toml_template_factory,
        poetry_toml_template_factory,
    ],
)
def test_template_factory_reads_packaged_resource(
    template_factory: Callable[[], str],
) -> None:
    """Each factory resolves its packaged resource via _read_template_from_resources."""
    assert template_factory()
