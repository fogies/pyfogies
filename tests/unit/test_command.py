"""Tests for fogies.tools.command."""

import io
import os
import pathlib
import sys
from unittest.mock import patch

import pytest

from fogies.tools.command import _resolve_command  # pyright: ignore[reportPrivateUsage]
from fogies.tools.command import CommandParams, command_run


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
    # No executable at the path, so use the path as given.
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


@pytest.mark.parametrize("in_stream", [True, False])
def test_command_run_in_stream(
    in_stream: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """command_run succeeds for both in_stream values.

    Regression test: command_run previously passed in_stream=True
    to invoke's context.run(), crashing when it tried to read() from True.

    Uses an immediately-EOF stdin because
    pytest's stdin intentionally raises on read().
    """
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    result = command_run(
        command=pathlib.Path(sys.executable),
        command_params=CommandParams(in_stream=in_stream),
        args=["-c", "print('test_command_run_in_stream')"],
    )
    assert result.stdout.strip() == "test_command_run_in_stream"


@pytest.mark.parametrize("hide", [True, False])
def test_command_run_hide(
    hide: bool,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """hide=True suppresses the live echo of a command's stdout; result.stdout still captures it either way."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    result = command_run(
        command=pathlib.Path(sys.executable),
        command_params=CommandParams(hide=hide),
        args=["-c", "print('test_command_run_hide')"],
    )
    assert result.stdout.strip() == "test_command_run_hide"
    echoed = "test_command_run_hide" in capsys.readouterr().out
    assert echoed == (not hide)


@pytest.mark.parametrize("echo_stdin", [True, False])
def test_command_run_echo_stdin(
    echo_stdin: bool,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """echo_stdin=True mirrors forwarded stdin back to output; False (the default) does not."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("test_command_run_echo_stdin\n"))
    result = command_run(
        command=pathlib.Path(sys.executable),
        command_params=CommandParams(echo_stdin=echo_stdin),
        # Reads and discards a line; prints nothing itself, so any occurrence
        # of the input text in captured output can only be invoke's mirroring.
        args=["-c", "import sys; sys.stdin.readline()"],
    )
    _ = result
    echoed = "test_command_run_echo_stdin" in capsys.readouterr().out
    assert echoed == echo_stdin
