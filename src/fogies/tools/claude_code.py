"""Tool wrapping the Claude Code CLI, and its sessions.

See <https://code.claude.com/docs>. The CLI is downloaded as the official
installer downloads it, rather than borrowing the copy bundled with the Claude
desktop app, whose location depends on how the app was installed and whose
version changes when the app updates.

Its main use here is resuming in the desktop app a session the app does not
list. The app's sidebar lists only sessions it started on this machine, and its
`/resume` lists only sessions started from the CLI, so a session started in the
app on another machine and synced here (e.g., by claude-sync) appears in
neither. `claude --desktop --resume` opens any of them.

The CLI signs in separately from the desktop app, so it needs signing in once
on each machine, with a Claude account rather than an API key.

Sessions are listed with the Claude Agent SDK, which tasks call directly. See <https://code.claude.com/docs/en/agent-sdk/python>. This is what
is wanted on top of it: finding a session from part of its ID, and describing
one in a line.
"""

import datetime
import pathlib
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager

from claude_agent_sdk import SDKSessionInfo

from fogies.download_verified import download_verified

# Most recent first; the first is the default. Each maps to the SHA-256 of its
# win32-x64 binary, from <version>/manifest.json under _DOWNLOAD_BASE_URL.
# Versions must be >= 2.1.285, which added `--desktop`.
_KNOWN_VERSIONS = {
    "2.1.287": "6d5be51f0edfe3429cd1a9885950db31c1e59eb9a2c9a30a47e64179d2ff98b4",
}

_DEFAULT_VERSION = next(iter(_KNOWN_VERSIONS))

_DOWNLOAD_BASE_URL = "https://downloads.claude.ai/claude-code-releases"

_CLAUDE_CODE_URL_TEMPLATE = _DOWNLOAD_BASE_URL + "/{version}/win32-x64/claude.exe"

# Longest title shown in a line describing a session.
_TITLE_LENGTH = 60


class _ClaudeCode:
    """Represents a Claude Code binary.

    Commands run attached to this process's console rather than through
    fogies.tools.command, because `--desktop` refuses to run with its output
    redirected, and signing in is interactive.
    """

    _version: str
    _path: pathlib.Path

    def __init__(self, *, version: str, path: pathlib.Path) -> None:
        self._version = version
        self._path = path

    @property
    def binary_version(self) -> str:
        """The Claude Code binary version string."""
        return self._version

    @property
    def binary_path(self) -> pathlib.Path:
        """The path to the Claude Code executable."""
        return self._path

    def _run(self, *, args: list[str], cwd: pathlib.Path | None = None) -> None:
        _ = subprocess.run([str(self._path)] + args, cwd=cwd, check=True)

    def auth_login(self) -> None:
        """Run `claude auth login`, signing in interactively."""
        self._run(args=["auth", "login"])

    def auth_logout(self) -> None:
        """Run `claude auth logout`, signing out."""
        self._run(args=["auth", "logout"])

    def auth_status(self) -> bool:
        """Run `claude auth status`, and return whether anyone is signed in.

        Shows who is signed in. Not being signed in is an exit code of 1, which
        is its answer rather than a failure, and is left to the caller to report.
        """
        command = [str(self._path), "auth", "status", "--text"]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode not in (0, 1):
            raise subprocess.CalledProcessError(
                result.returncode, command, result.stdout, result.stderr
            )
        if result.returncode == 0:
            print(result.stdout, end="")
        return result.returncode == 0

    def resume_in_desktop(self, *, session_id: str, cwd: pathlib.Path) -> None:
        """Run `claude --desktop --resume`, opening a session in the desktop app.

        It runs in the directory the session ran in, which must exist on this
        machine. A session open in another terminal is not moved.
        """
        if not cwd.is_dir():
            raise ValueError(
                "Session '{}' ran in '{}', which does not exist here".format(
                    session_id,
                    cwd,
                )
            )
        self._run(args=["--desktop", "--resume", session_id], cwd=cwd)


@contextmanager
def claude_code(
    *,
    version: str | None = None,
    binary_cache_path: pathlib.Path,
) -> Generator[_ClaudeCode]:
    """Download a Claude Code binary (if not cached) and yield a handle.

    *version* when None uses the bundled default Claude Code version.
    Downloaded into a version-specific subdirectory of binary_cache_path,
    keeping the binary's own name.
    """
    if sys.platform != "win32":
        raise RuntimeError("Only implemented on Windows")

    if version is None:
        version = _DEFAULT_VERSION

    if version not in _KNOWN_VERSIONS:
        known = ", ".join(_KNOWN_VERSIONS)
        raise ValueError(
            "Unknown Claude Code version '{}'; known versions: {}".format(
                version,
                known,
            )
        )

    exe_path = (
        binary_cache_path
        / "claude_code_{}".format(version.replace(".", "_"))
        / "claude.exe"
    )

    if not exe_path.exists():
        exe_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            url = _CLAUDE_CODE_URL_TEMPLATE.format(version=version)
            _ = exe_path.write_bytes(
                download_verified(url=url, sha256=_KNOWN_VERSIONS[version])
            )
        except Exception:
            exe_path.unlink(missing_ok=True)
            raise

    yield _ClaudeCode(version=version, path=exe_path)


def find_session_id(session_ids: list[str], value: str) -> str:
    """Return the session ID that value identifies, from any part of it.

    That includes the start of it, as with git, and all of it. Raises
    ValueError if no ID has the part, or if more than one does.
    """
    wanted = value.strip().lower()
    if not wanted:
        raise ValueError("Give at least part of a session's ID.")

    matches = [i for i in session_ids if wanted in i.lower()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ValueError(
            "'{}' matches {} sessions: {}. Give more of it.".format(
                value, len(matches), ", ".join(matches)
            )
        )
    raise ValueError("No session '{}'".format(value))


def describe_session(session: SDKSessionInfo) -> str:
    """Return a line describing a session: its ID, when it was modified, where it ran, and its title."""
    # The transcript's modified time. For a session synced from another
    # machine (e.g., by claude-sync), that is when it was synced.
    modified = (
        datetime.datetime.fromtimestamp(session.last_modified / 1000)
        .astimezone()
        .strftime("%Y-%m-%d %H:%M")
    )
    project = pathlib.Path(session.cwd).name if session.cwd is not None else "?"
    title = " ".join((session.summary or "").split())
    if len(title) > _TITLE_LENGTH:
        title = title[: _TITLE_LENGTH - 3] + "..."
    return "{}  {}  {:<24}  {}".format(session.session_id, modified, project, title)
