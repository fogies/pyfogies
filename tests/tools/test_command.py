"""Tests for fogies.tools.command."""

import os
import pathlib
from unittest.mock import patch

import pytest

from fogies.tools.command import _resolve_command  # pyright: ignore[reportPrivateUsage]
from fogies.tools.command import CommandParams


def test_require_cwd_sets_cwd() -> None:
    """require_cwd returns a new instance with cwd set when cwd is None."""
    path = pathlib.Path("/some/dir")
    params = CommandParams()
    result = params.require_cwd(path)
    assert result is not params
    assert result.cwd == path


def test_require_cwd_returns_self() -> None:
    """require_cwd returns self when cwd already equals path."""
    path = pathlib.Path("/some/dir")
    params = CommandParams(cwd=path)
    result = params.require_cwd(path)
    assert result is params


def test_require_cwd_raises() -> None:
    """require_cwd raises ValueError when cwd is set to a different path."""
    path = pathlib.Path("/some/dir")
    params = CommandParams(cwd=path)
    with pytest.raises(ValueError):
        _ = params.require_cwd(pathlib.Path("/other"))


def test_resolve_command_no_cwd() -> None:
    """With no cwd, the command is assumed correct and returned as given."""
    cmd_in_path = pathlib.Path("command")
    cmd_executable = pathlib.Path("bin") / "binary.exe"
    assert _resolve_command(cmd_in_path, None) == str(cmd_in_path)
    assert _resolve_command(cmd_executable, None) == str(cmd_executable)


def test_resolve_command_with_cwd_in_path() -> None:
    """With cwd set, a command that does not point to a file should resolve on the path."""
    cwd = pathlib.Path("workingdir", "workingdir")
    cmd_in_path = pathlib.Path("command")
    # No executable at that path, so use the path as given.
    with patch.object(pathlib.Path, "exists", return_value=False):
        assert _resolve_command(cmd_in_path, cwd) == str(cmd_in_path)


def test_resolve_command_with_cwd_executable(
    tmp_path: pathlib.Path,
) -> None:
    """With cwd set, a command that points to an existing file is made relative to cwd."""
    cwd = pathlib.Path(tmp_path, "workingdir", "workingdir")
    cmd_executable = pathlib.Path(tmp_path, "bin", "binary.exe")
    cmd_executable.parent.mkdir(parents=True, exist_ok=True)
    _ = cmd_executable.write_bytes(b"")
    expected = os.path.relpath(str(cmd_executable), str(cwd))
    assert _resolve_command(cmd_executable, cwd) == expected
