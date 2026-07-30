"""Test fogies.tasks.terraform get_task_apply/get_task_destroy."""

import io
import pathlib
import sys

import pytest
from invoke.context import Context
from pydantic import BaseModel

from fogies.tasks.terraform import get_task_apply, get_task_destroy
from tasks.paths import PATH_STAGING_BINARY_CACHE

_MODULE_PATH = pathlib.Path(__file__).parent


class _TasksTerraformOutput(BaseModel):
    file_path: str
    file_content: str


def test_task_apply_and_destroy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """apply creates the resource and returns output; destroy removes it."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    expected_file_path = _MODULE_PATH / "test_resource.txt"

    task_apply = get_task_apply(
        module_path=_MODULE_PATH,
        binary_cache_path=PATH_STAGING_BINARY_CACHE,
        default_apply_auto_approve=True,
        default_output=True,
        output_model=_TasksTerraformOutput,
    )
    task_destroy = get_task_destroy(
        module_path=_MODULE_PATH,
        binary_cache_path=PATH_STAGING_BINARY_CACHE,
        default_destroy_auto_approve=True,
    )

    try:
        _ = task_apply(Context())
        assert expected_file_path.exists()
        assert expected_file_path.read_text().strip() == "test_task_apply_and_destroy"
    finally:
        _ = task_destroy(Context())
        assert not expected_file_path.exists()
