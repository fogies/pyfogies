"""Tool wrapping claude-sync, built with a portable Go toolchain.

See <https://github.com/tawanorg/claude-sync>. claude-sync ships no Windows
release binary, so it's built from source here rather than downloaded
pre-built, unlike fogies.tools.terraform. Only push/pull/status are wrapped;
claude-sync's own storage setup (S3/R2/etc. credentials, bucket, encryption
passphrase) is configured through `claude-sync init`'s interactive wizard,
which is out of scope here.
"""

import pathlib
from collections.abc import Generator
from contextlib import contextmanager

from invoke.runners import Result

from fogies.tools.command import CommandParams, command_run
from fogies.tools.go import go

# Most recent first; _KNOWN_VERSIONS[0] is the default.
_KNOWN_VERSIONS = [
    "1.17.1",
]

_DEFAULT_VERSION = _KNOWN_VERSIONS[0]

_MODULE_TEMPLATE = "github.com/tawanorg/claude-sync/cmd/claude-sync@v{version}"


class _ClaudeSync:
    """Represents a claude-sync binary."""

    _path: pathlib.Path

    def __init__(self, *, path: pathlib.Path) -> None:
        self._path = path

    @property
    def binary_path(self) -> pathlib.Path:
        """The path to the claude-sync executable."""
        return self._path

    def push(self, *, command_params: CommandParams, quiet: bool = False) -> Result:
        """Run `claude-sync push`, uploading local changes to cloud storage."""
        push_args = ["push"]
        if quiet:
            push_args.append("-q")
        return command_run(
            command=self.binary_path,
            command_params=command_params,
            args=push_args,
        )

    def pull(
        self,
        *,
        command_params: CommandParams,
        dry_run: bool = False,
        force: bool = False,
        quiet: bool = False,
    ) -> Result:
        """Run `claude-sync pull`, downloading remote changes."""
        pull_args = ["pull"]
        if dry_run:
            pull_args.append("--dry-run")
        if force:
            pull_args.append("--force")
        if quiet:
            pull_args.append("-q")
        return command_run(
            command=self.binary_path,
            command_params=command_params,
            args=pull_args,
        )

    def status(self, *, command_params: CommandParams) -> Result:
        """Run `claude-sync status`, showing pending local changes."""
        return command_run(
            command=self.binary_path,
            command_params=command_params,
            args=["status"],
        )


@contextmanager
def claude_sync(
    *,
    version: str | None = None,
    binary_cache_path: pathlib.Path,
    raise_if_env_exists: bool,
) -> Generator[_ClaudeSync]:
    """Build claude-sync with a portable Go toolchain (if not cached) and yield a handle.

    *version* when None uses the bundled default claude-sync version. Built
    into a version-specific subdirectory of binary_cache_path (matching
    fogies.tools.go's own SDK caching), so bumping the pinned version
    triggers a fresh build rather than silently reusing a stale binary.

    raise_if_env_exists has no default; see fogies.tools.environ.environ()
    for why. Passed through to go().install()'s own GOBIN isolation.
    """
    if version is None:
        version = _DEFAULT_VERSION

    if version not in _KNOWN_VERSIONS:
        known = ", ".join(_KNOWN_VERSIONS)
        raise ValueError(
            "Unknown claude-sync version '{}'; known versions: {}".format(
                version, known
            )
        )

    gobin_path = binary_cache_path / "claude_sync_{}".format(version.replace(".", "_"))
    exe_path = gobin_path / "claude-sync.exe"

    if not exe_path.exists():
        with go(binary_cache_path=binary_cache_path) as go_tool:
            _ = go_tool.install(
                command_params=CommandParams(in_stream=False),
                module=_MODULE_TEMPLATE.format(version=version),
                gobin_path=gobin_path,
                raise_if_env_exists=raise_if_env_exists,
            )

    if not exe_path.exists():
        raise RuntimeError("claude-sync executable not found in '{}'".format(gobin_path))

    yield _ClaudeSync(path=exe_path)
