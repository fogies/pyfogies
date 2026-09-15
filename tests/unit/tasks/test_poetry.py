"""Tests for fogies.tasks.poetry."""

from pathlib import Path

import pytest
from invoke.context import Context

from fogies.tasks.poetry import get_task_publish


def test_get_task_publish_raises_for_missing_file(tmp_path: Path) -> None:
    """task_publish creates a template and raises, rather than reading it."""
    path_secrets_poetry = tmp_path / "poetry.toml"
    assert not path_secrets_poetry.exists()

    task_publish = get_task_publish(path_secrets_poetry=path_secrets_poetry)

    with pytest.raises(FileNotFoundError, match="was not found"):
        _ = task_publish(Context())

    assert path_secrets_poetry.exists()
