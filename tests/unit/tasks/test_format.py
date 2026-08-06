"""Tests for fogies.tasks.format."""

import pytest

from fogies.tasks.format import get_task_format


def test_get_task_format_raises_when_all_flags_false() -> None:
    """get_task_format raises when every fmt_* flag is False (would be a no-op)."""
    with pytest.raises(ValueError):
        _ = get_task_format()


def test_get_task_format_raises_when_terraform_missing_cache_path() -> None:
    """get_task_format raises when fmt_terraform is set without a cache path."""
    with pytest.raises(ValueError):
        _ = get_task_format(fmt_terraform=True)
