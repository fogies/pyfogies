"""Tool wrapping claude-sync, built with a portable Go toolchain.

See <https://github.com/tawanorg/claude-sync>. claude-sync ships no Windows
release binary, so it's built from source here rather than downloaded
pre-built, unlike fogies.tools.terraform. Only push/pull/status/conflicts are
wrapped.

claude-sync's own setup wizard (`claude-sync init`) can't run unattended: for
S3 it prompts for the credentials, region and bucket even when they are given
as flags, and for the passphrase its encryption key can be derived from. So a
machine is set up by writing the files claude-sync reads, from one
gitignored config that is synced between machines like the other secrets. That
config holds the encryption key itself, not a passphrase; see fogies.age_key.
The credentials are not in it, but in a profile of the AWS config.

The files claude-sync reads are managed only from that config, not with
claude-sync's own commands. They are compared exactly, so changing them any
other way makes them differ from it.
"""

import dataclasses
import json
import pathlib
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Literal

import tomlkit
from invoke.runners import Result
from pydantic import BaseModel, ValidationError, field_validator

from fogies.age_key import generate_age_key, validate_age_key
from fogies.config import load_config, resolve_config_path
from fogies.templates import claude_sync_toml_template_factory
from fogies.tools.aws_environ import AwsProfile, load_aws_profile_from_config
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


def _had_errors(output: str) -> bool:
    """Return whether the output of a pull or a push says that some files failed.

    claude-sync exits successfully even then, and only prints them.
    """
    return "Errors:" in output


def _pull_finished(output: str) -> bool:
    """Return whether the output of a pull says that it ran to its end.

    A pull that does nothing, or is stopped (e.g., a first pull that is
    aborted), exits successfully too. What every pull that runs to its end
    prints, as it is always asked to rebuild the history, is that it did. The
    messages for a pull with nothing to download, or one that is up to date,
    are not printed in every case, so are not relied on.
    """
    return "Rebuilt history.jsonl" in output


def _conflicts_remain(output: str) -> bool:
    """Return whether the output of listing conflicts is not that there are none.

    Anything else, including wording that is not recognized, counts as there
    being some, so that a change in what claude-sync prints stops a push rather
    than allowing one.
    """
    return "No conflicts found" not in output


def claude_directory() -> pathlib.Path:
    """Where claude-sync syncs from, which is not configurable."""
    return pathlib.Path.home() / ".claude"


def claude_sync_files_directory() -> pathlib.Path:
    """Where the claude-sync files are: its config.yaml and encryption key."""
    return pathlib.Path.home() / _DIRECTORY_NAME


class _SyncState(BaseModel):
    """What claude-sync records of syncing, of which only the files matter."""

    files: dict[str, object] = {}


def is_first_pull() -> bool:
    """Return whether claude-sync has recorded nothing of syncing on this machine.

    If it is not sure, it is taken to be, because what follows is forcing the
    pull. If it is wrong the other way, claude-sync asks about overwriting files
    before its first pull, which does not work from a task.
    """
    try:
        state = _SyncState.model_validate_json(
            (claude_sync_files_directory() / "state.json").read_text(encoding="utf-8")
        )
    except OSError, ValidationError:
        return True
    return not state.files


class ClaudeSyncConfig(BaseModel):
    """Contents of the claude-sync config."""

    # A profile in the AWS config, with the credentials claude-sync signs in with.
    aws_profile: str
    bucket: str
    region: str
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
    return load_config(
        path=path,
        model=ClaudeSyncConfig,
        template_factory=claude_sync_toml_template_factory,
    )


def update_claude_sync_config(*, path: pathlib.Path, age_key: str) -> None:
    """Update the config with age_key, keeping its comments and layout.

    If the config redirects, the shared config it redirects to is updated.
    """
    path = resolve_config_path(path=path)
    with path.open("r", encoding="utf-8") as f:
        doc = tomlkit.parse(f.read())
    doc["age_key"] = age_key
    with path.open("w", encoding="utf-8", newline="\n") as f:
        _ = f.write(tomlkit.dumps(doc))


def render_claude_sync_yaml(config: ClaudeSyncConfig, aws_profile: AwsProfile) -> str:
    """Return the contents of claude-sync's config.yaml for config and aws_profile.

    As `claude-sync init` writes for S3, except that the scope is always
    written, not left out when it's the default. Values are written as JSON
    strings, which are also valid YAML strings, so that none needs escaping.
    """
    lines = [
        "storage:",
        "    provider: s3",
        "    bucket: " + json.dumps(config.bucket),
        "    access_key_id: " + json.dumps(aws_profile.aws_access_key_id),
        "    secret_access_key: " + json.dumps(aws_profile.aws_secret_access_key),
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
    *, claude_sync_config_path: pathlib.Path, aws_config_path: pathlib.Path, force: bool
) -> ClaudeSyncConfigureResult:
    """Apply the config at claude_sync_config_path to the claude-sync files.

    The credentials are those of the config's profile in the AWS config at
    aws_config_path.

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
    config = load_claude_sync_config(path=claude_sync_config_path)
    aws_profile = load_aws_profile_from_config(
        config_path=aws_config_path, profile_name=config.aws_profile
    )
    generated_age_key = config.age_key is None
    age_key = generate_age_key() if config.age_key is None else config.age_key

    # What the claude-sync files should contain.
    expected_content = {
        key_path: age_key + "\n",
        directory / _YAML_FILE_NAME: render_claude_sync_yaml(config, aws_profile),
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
        update_claude_sync_config(path=claude_sync_config_path, age_key=age_key)

    # Write the claude-sync files.
    directory.mkdir(parents=True, exist_ok=True)
    for path in paths_to_write:
        _ = path.write_text(expected_content[path], encoding="utf-8", newline="\n")

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

    def list_conflicts(self, *, command_params: CommandParams) -> Result:
        """Run `claude-sync conflicts --list`, listing conflicts from a sync.

        When both the local and remote file change, the remote version is saved
        as a .conflict file.
        """
        return command_run(
            command=self.binary_path,
            command_params=command_params,
            args=["conflicts", "--list"],
        )

    def resolve_conflicts(
        self,
        *,
        command_params: CommandParams,
        keep: Literal["local", "remote"] | None = None,
    ) -> Result:
        """Run `claude-sync conflicts`, resolving conflicts from a sync.

        By default they are resolved interactively, where showing differences
        runs a `diff` command, so one has to be on PATH. *keep* resolves all of
        them, keeping the local or the remote version.
        """
        resolve_args = ["conflicts"]
        if keep is not None:
            resolve_args.extend(["--keep", keep])
        return command_run(
            command=self.binary_path,
            command_params=command_params,
            args=resolve_args,
        )

    def push(
        self,
        *,
        command_params: CommandParams,
        include_mcp: bool = False,
    ) -> Result:
        """Run `claude-sync push`, uploading local changes to cloud storage."""
        push_args = ["push"]
        if include_mcp:
            push_args.append("--include-mcp")
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
    ) -> Result:
        """Run `claude-sync pull`, downloading remote changes.

        The history is always rebuilt afterward, from the session files, because
        otherwise history.jsonl, which is a single file that machines replace
        each other's copies of, loses entries. (Nothing is rebuilt for a dry run.)

        The first pull on a machine merges what is in the bucket with what is
        here, the newer of a file on both sides winning, and claude-sync asks
        whether to back up first. The prompt does not work from a task, and the
        bucket keeps earlier versions of what was pushed, so it is skipped with
        --force. A dry run shows what that would do, without it.
        """
        pull_args = ["pull", "--rebuild-history"]
        if dry_run:
            pull_args.append("--dry-run")
        elif is_first_pull():
            force = True
        if force:
            pull_args.append("--force")
        if include_mcp:
            pull_args.append("--include-mcp")
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

    def _conflicts_remain(self, *, command_params: CommandParams) -> bool:
        """Return whether conflicts are left, according to listing them."""
        return _conflicts_remain(
            self.list_conflicts(command_params=command_params).stdout
        )

    def sync(
        self,
        *,
        command_params: CommandParams,
        unattended: bool = False,
        after_pull: Callable[[], None] | None = None,
    ) -> None:
        """Pull, resolve any conflicts, and then push.

        A push does not look at what is in the bucket, so pushing without
        pulling replaces other machines' changes, and pushing with conflicts
        unresolved replaces the bucket's version with this machine's. So the
        history is rebuilt after the pull, and conflicts are resolved
        interactively.

        *after_pull* is called once the pull, and any conflicts, are done, and
        before the push, so that what it changes (e.g., files it deletes because
        another machine did) is what is pushed. It is not called if the sync
        stops before then, and if it raises, nothing is pushed.

        *unattended* when true never asks, so what would need resolving stops
        it. Conflicts left from before also stop it before it pulls, which would
        otherwise add to them. The first sync on a machine merges what is here
        with the bucket, so it is not unattended.

        Raises ValueError, without pushing, if the pull had errors or did not
        finish, or conflicts are unresolved (e.g., skipped). Raises it after
        pushing, which is not undone, if the push had errors.
        """
        if unattended and is_first_pull():
            raise ValueError("The first sync on this machine has to be attended.")

        hidden = dataclasses.replace(command_params, hide=True)
        if unattended and self._conflicts_remain(command_params=hidden):
            raise ValueError("Not syncing, because conflicts are unresolved.")

        pull_result = self.pull(command_params=command_params)
        if _had_errors(pull_result.stdout):
            raise ValueError("Not pushing, because the pull had errors.")
        if not _pull_finished(pull_result.stdout):
            raise ValueError("Not pushing, because the pull did not finish.")

        if unattended:
            if self._conflicts_remain(command_params=hidden):
                raise ValueError("Not pushing, because the pull had conflicts.")
        elif self._conflicts_remain(command_params=command_params):
            _ = self.resolve_conflicts(command_params=command_params)
            # What was resolved was already shown, so only what is left is.
            if self._conflicts_remain(command_params=hidden):
                raise ValueError("Not pushing, because conflicts are unresolved.")

        if after_pull is not None:
            after_pull()

        push_result = self.push(command_params=command_params)
        if _had_errors(push_result.stdout):
            raise ValueError("The push had errors, so some files were not uploaded.")


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
