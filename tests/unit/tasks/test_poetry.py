"""Tests for fogies.tasks.poetry."""

from pathlib import Path

import pytest
from invoke.context import Context

from fogies.tasks.poetry import get_task_publish


def test_get_task_publish_raises_for_missing_file(tmp_path: Path) -> None:
    """task_publish creates a template and raises, rather than reading it."""
    secrets_poetry_path = tmp_path / "poetry.toml"
    assert not secrets_poetry_path.exists()

    task_publish = get_task_publish(secrets_poetry_path=secrets_poetry_path)

    with pytest.raises(FileNotFoundError, match="was not found"):
        _ = task_publish(Context())

    assert secrets_poetry_path.exists()
