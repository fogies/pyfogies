"""Tool wrapping claude-sync, built with a portable Go toolchain.

See <https://github.com/tawanorg/claude-sync>. claude-sync ships no Windows
release binary, so it's built from source here rather than downloaded
pre-built, unlike fogies.tools.terraform. Only push/pull/status are wrapped.

claude-sync's own setup wizard (`claude-sync init`) can't run unattended: for
S3 it prompts for the credentials, region and bucket even when they are given
as flags, and for the passphrase its encryption key can be derived from. So a
machine is set up by writing the files claude-sync reads, from one
gitignored config that is synced between machines like the other secrets. That
config holds the encryption key itself, not a passphrase; see fogies.age_key.

The files claude-sync reads are managed only from that config, not with
claude-sync's own commands. They are compared exactly, so changing them any
other way makes them differ from it.
"""

import dataclasses
import json
import pathlib
import tomllib
from collections.abc import Generator
from contextlib import contextmanager
from typing import Literal

import tomlkit
from invoke.runners import Result
from pydantic import BaseModel, field_validator

from fogies.age_key import generate_age_key, validate_age_key
from fogies.templates import claude_sync_toml_template_factory, ensure_from_template
from fogies.tools.command import CommandParams, command_run
from fogies.tools.go import go

# Most recent first; _KNOWN_VERSIONS[0] is the default.
_KNOWN_VERSIONS = [
    "1.17.1",
]

_DEFAULT_VERSION = _KNOWN_VERSIONS[0]

_MODULE_TEMPLATE = "github.com/tawanorg/claude-sync/cmd/claude-sync@v{version}"

# The claude-sync files, in the home directory.
_DIRECTORY_NAME = ".claude-sync"
_YAML_FILE_NAME = "config.yaml"
_KEY_FILE_NAME = "age-key.txt"


def claude_sync_files_directory() -> pathlib.Path:
    """Where the claude-sync files are: its config.yaml and encryption key."""
    return pathlib.Path.home() / _DIRECTORY_NAME


class ClaudeSyncConfig(BaseModel):
    """Contents of the claude-sync config."""

    bucket: str
    region: str
    access_key_id: str
    secret_access_key: str
    scope: Literal["full", "sessions"]
    # Absent until created by configure.
    age_key: str | None = None

    @field_validator("age_key")
    @classmethod
    def _age_key_is_an_age_key(cls, value: str | None) -> str | None:
        return None if value is None else validate_age_key(value)


def load_claude_sync_config(*, path: pathlib.Path) -> ClaudeSyncConfig:
    """Return the config in path.

    If it doesn't exist yet, it is created from a template and FileNotFoundError
    is raised, so that it is filled in before it is used.
    """
    ensure_from_template(path=path, template_factory=claude_sync_toml_template_factory)
    with path.open("rb") as f:
        return ClaudeSyncConfig.model_validate(tomllib.load(f))


def update_claude_sync_config(*, path: pathlib.Path, age_key: str) -> None:
    """Update the config with age_key, keeping its comments and layout."""
    with path.open("r", encoding="utf-8") as f:
        doc = tomlkit.parse(f.read())
    doc["age_key"] = age_key
    with path.open("w", encoding="utf-8", newline="\n") as f:
        _ = f.write(tomlkit.dumps(doc))


def render_claude_sync_yaml(config: ClaudeSyncConfig) -> str:
    """Return the contents of claude-sync's config.yaml for config.

    As `claude-sync init` writes for S3, except that the scope is always
    written, not left out when it's the default. Values are written as JSON
    strings, which are also valid YAML strings, so that none needs escaping.
    """
    lines = [
        "storage:",
        "    provider: s3",
        "    bucket: " + json.dumps(config.bucket),
        "    access_key_id: " + json.dumps(config.access_key_id),
        "    secret_access_key: " + json.dumps(config.secret_access_key),
        "    region: " + json.dumps(config.region),
        "encryption_key_path: "
        + json.dumps("~/{}/{}".format(_DIRECTORY_NAME, _KEY_FILE_NAME)),
        "scope: " + config.scope,
    ]
    return "\n".join(lines) + "\n"


@dataclasses.dataclass(frozen=True)
class ClaudeSyncConfigureResult:
    """What configure_claude_sync() did."""

    generated_age_key: bool
    applied_to_claude_sync_files: bool


def configure_claude_sync(
    *, config_path: pathlib.Path, force: bool
) -> ClaudeSyncConfigureResult:
    """Apply the config at config_path to the claude-sync files.

    The config decides what claude-sync's encryption key and config.yaml
    should be, in claude_sync_files_directory(). If it has no key yet, a new one
    is generated and saved in it, so that other machines use it too.

    A claude-sync file that is missing is written, and one that already
    matches is left alone. One that differs is an error, and nothing is
    written, unless force is set, which replaces it.
    """
    # Where the claude-sync files are.
    directory = claude_sync_files_directory()
    key_path = directory / _KEY_FILE_NAME

    # The key in the config, or a new one if it has none.
    config = load_claude_sync_config(path=config_path)
    generated_age_key = config.age_key is None
    age_key = generate_age_key() if config.age_key is None else config.age_key

    # What the claude-sync files should contain.
    expected_content = {
        key_path: age_key + "\n",
        directory / _YAML_FILE_NAME: render_claude_sync_yaml(config),
    }
    # Which of them are missing or differ.
    paths_to_write = [
        path
        for path, text in expected_content.items()
        if not path.exists() or path.read_text(encoding="utf-8") != text
    ]
    # Which of those exist but differ.
    paths_that_differ = [path for path in paths_to_write if path.exists()]

    # Refuse to replace what differs, unless forced.
    if paths_that_differ and not force:
        raise ValueError("Config does not match existing claude-sync files.")

    # Save a generated key in the config, for other machines.
    if generated_age_key:
        update_claude_sync_config(path=config_path, age_key=age_key)

    # Write the claude-sync files.
    directory.mkdir(parents=True, exist_ok=True)
    for path in paths_to_write:
        _ = path.write_text(expected_content[path], encoding="utf-8", newline="\n")
        path.chmod(0o600)

    return ClaudeSyncConfigureResult(
        generated_age_key=generated_age_key,
        applied_to_claude_sync_files=bool(paths_to_write),
    )


class _ClaudeSync:
    """Represents a claude-sync binary."""

    _path: pathlib.Path

    def __init__(self, *, path: pathlib.Path) -> None:
        self._path = path

    @property
    def binary_path(self) -> pathlib.Path:
        """The path to the claude-sync executable."""
        return self._path

    def push(
        self,
        *,
        command_params: CommandParams,
        include_mcp: bool = False,
        quiet: bool = False,
    ) -> Result:
        """Run `claude-sync push`, uploading local changes to cloud storage."""
        push_args = ["push"]
        if include_mcp:
            push_args.append("--include-mcp")
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
        include_mcp: bool = False,
        quiet: bool = False,
        rebuild_history: bool = False,
    ) -> Result:
        """Run `claude-sync pull`, downloading remote changes."""
        pull_args = ["pull"]
        if dry_run:
            pull_args.append("--dry-run")
        if force:
            pull_args.append("--force")
        if include_mcp:
            pull_args.append("--include-mcp")
        if quiet:
            pull_args.append("-q")
        if rebuild_history:
            pull_args.append("--rebuild-history")
        return command_run(
            command=self.binary_path,
            command_params=command_params,
            args=pull_args,
        )

    def status(self, *, command_params: CommandParams, quiet: bool = False) -> Result:
        """Run `claude-sync status`, showing pending local changes."""
        status_args = ["status"]
        if quiet:
            status_args.append("-q")
        return command_run(
            command=self.binary_path,
            command_params=command_params,
            args=status_args,
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
        raise RuntimeError(
            "claude-sync executable not found in '{}'".format(gobin_path)
        )

    yield _ClaudeSync(path=exe_path)
