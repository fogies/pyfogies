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
import hashlib
import json
import locale
import pathlib
import re
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


# What claude-sync prints, which is all that is known of how a command went:
# a pull or a push that has failures exits successfully, and only prints them.
# So what is read from the output is only trusted if every line of it is one of
# the forms below, as claude-sync prints them (without colours). A line that is
# not one means its output has changed from what was checked, which stops what
# is being done instead of being missed. These are as of _KNOWN_VERSIONS[0], from
# everything its source prints in these commands (cmd/claude-sync/main.go, and
# the log() in internal/sync/sync.go, which is not in the commands themselves),
# so check them when changing that.
#
# A path, or the message of an error, in a line is matched as any text.


def _symbol(symbol: str) -> str:
    """Return the pattern of a symbol that begins a line, and the space after it.

    claude-sync prints it as UTF-8, which reaches here decoded as the locale
    decodes bytes (e.g., cp1252 on Windows, unless it is UTF-8), so it is also
    matched as that.
    """
    variants = {symbol}
    for encoding in {"cp1252", locale.getpreferredencoding(False)}:
        variants.add(symbol.encode("utf-8").decode(encoding, errors="replace"))
    return "(?:{}) ".format("|".join(re.escape(v) for v in sorted(variants)))


_DONE = _symbol("✓")
_FAILED = _symbol("✗")
_SCANNING = _symbol("⋯")
_UPLOADING = _symbol("↑")
_DOWNLOADING = _symbol("↓")
_CONFLICT = _symbol("⚠")
_BULLET = _symbol("•")


def _forms(*patterns: str) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def _summary(*names: str) -> str:
    """Return the pattern of the counts in the summary of a pull or a push."""
    count = r"\d+ (?:{})".format("|".join(names))
    return r"{}(?:, {})*".format(count, count)


# Printed by both a pull and a push.
_PROGRESS_FORMS = _forms(
    # A path being scanned.
    _SCANNING + r".+",
    # A path that failed, and why.
    _FAILED + r".+: .+",
    # An error, or a conflict, in a list.
    _BULLET + r".+",
    r"Errors:",
)

_PUSH_FORMS = _PROGRESS_FORMS + _forms(
    _UPLOADING + r"\[\d+/\d+\] .+ \(.+\)",
    _FAILED + r"\[\d+/\d+\] .+ \(deleted\)",
    _DONE + r"No changes to push",
    _DONE + r"Push complete: " + _summary("uploaded", "deleted", "failed"),
    # A warning that it goes on from, which is not a file that failed.
    r"Warning: failed to upload manifest: .+",
)

_PULL_FORMS = _PROGRESS_FORMS + _forms(
    _DOWNLOADING + r"\[\d+/\d+\] .+ \(.+\)",
    _CONFLICT + r"Conflict: .+ \(saved as \.conflict\)",
    r"Conflict detected: .+ \(keeping local, saving remote as \.conflict\)",
    # A warning that it goes on from, which is not a file that failed.
    r"Warning: failed to restore mtime for .+: .+",
    _DONE + r"Already up to date",
    _DONE + r"Pull complete: " + _summary("downloaded", "conflicts", "failed"),
    r"Conflicts \(both local and remote changed\):",
    r"Local versions kept\. Remote saved as \.conflict files\.",
    r"Run 'claude-sync conflicts' to review and resolve\.",
    r"Rebuilt history\.jsonl: \d+ entries \(\d+ existing \+ \d+ recovered from sessions\)",
)

_CONFLICTS_NONE = re.compile(_DONE + r"No conflicts found")
_CONFLICTS_FORMS = [
    _CONFLICTS_NONE,
    *_forms(
        r"Found \d+ conflict\(s\):",
        r"\d+\. .+",
        r"Conflict from: .+",
    ),
]

_COLOURS = re.compile(r"\x1b\[[0-9;]*m")


def _lines(*, command: str, output: str, forms: list[re.Pattern[str]]) -> list[str]:
    """Return the lines of the output of a claude-sync command, without colours.

    Progress is printed over itself with carriage returns, so those separate
    lines too. Raises ValueError if a line is not one of forms.
    """
    lines = [
        line.strip()
        for line in _COLOURS.sub("", output).replace("\r", "\n").split("\n")
        if line.strip()
    ]
    for line in lines:
        if not any(form.fullmatch(line) for form in forms):
            raise ValueError(
                "claude-sync's {} printed '{}', which is not recognised, so how it went is not known. Its output may have changed from what was checked.".format(
                    command, line
                )
            )
    return lines


def _had_errors(*, command: Literal["pull", "push"], output: str) -> bool:
    """Return whether the output of a pull or a push says that some files failed.

    Raises ValueError if the output is not recognised.
    """
    forms = _PULL_FORMS if command == "pull" else _PUSH_FORMS
    return "Errors:" in _lines(command=command, output=output, forms=forms)


def _pull_finished(output: str) -> bool:
    """Return whether the output of a pull says that it ran to its end.

    A pull that does nothing, or is stopped (e.g., a first pull that is
    aborted), exits successfully too. What every pull that runs to its end
    prints, as it is always asked to rebuild the history, is that it did. The
    messages for a pull with nothing to download, or one that is up to date,
    are not printed in every case, so are not relied on. Raises ValueError if
    the output is not recognised.
    """
    return any(
        line.startswith("Rebuilt history.jsonl")
        for line in _lines(command="pull", output=output, forms=_PULL_FORMS)
    )


def _conflicts_remain(output: str) -> bool:
    """Return whether the output of listing conflicts says that there are some.

    Raises ValueError if the output is not recognised, or says neither that
    there are none nor how many there are.
    """
    lines = _lines(command="conflicts", output=output, forms=_CONFLICTS_FORMS)
    if any(_CONFLICTS_NONE.fullmatch(line) for line in lines):
        return False
    if any(line.startswith("Found ") for line in lines):
        return True
    raise ValueError(
        "claude-sync's conflicts printed neither that there are none nor how many there are, so whether there are any is not known."
    )


def claude_directory() -> pathlib.Path:
    """Where claude-sync syncs from, which is not configurable."""
    return pathlib.Path.home() / ".claude"


def claude_sync_files_directory() -> pathlib.Path:
    """Where the claude-sync files are: its config.yaml and encryption key."""
    return pathlib.Path.home() / _DIRECTORY_NAME


# What claude-sync syncs under the Claude directory, by what its scope is, as of
# _KNOWN_VERSIONS[0] (SessionSyncPaths and SyncPaths in its
# internal/config/config.go, so check them when changing that). A name is a
# file, or a directory with everything in it.
SESSIONS_PATHS = ["projects", "history.jsonl", "tasks", "plans"]
_FULL_PATHS = [
    "CLAUDE.md",
    "settings.json",
    "settings.local.json",
    "agents",
    "commands",
    "skills",
    "plugins",
    "projects",
    "plans",
    "tasks",
    "history.jsonl",
    "rules",
    "workflows",
]

_SCOPE_LINE = re.compile(r"""^scope:\s*["']?(\w+)["']?\s*$""", re.MULTILINE)


def synced_paths() -> list[str]:
    """Return what claude-sync syncs on this machine, by names in claude_directory().

    That is as its scope says, in its config.yaml, which is what it reads. As it
    does, anything but the sessions scope, including having none, is the full
    scope.
    """
    try:
        text = (claude_sync_files_directory() / _YAML_FILE_NAME).read_text(
            encoding="utf-8"
        )
    except OSError:
        return _FULL_PATHS
    scope = _SCOPE_LINE.search(text)
    return SESSIONS_PATHS if scope and scope[1] == "sessions" else _FULL_PATHS


_STATE_FILE_NAME = "state.json"


class _RecordedFile(BaseModel):
    """What claude-sync records of a file it synced, of which only the hash matters.

    The hash is not required, so that a file recorded in some other form still
    counts as recorded for is_first_pull, where not being sure means forcing the
    pull. Where the hash is needed, a file without one is as if not recorded.
    """

    hash: str | None = None


class _SyncState(BaseModel):
    """What claude-sync records of syncing, of which only the files matter.

    The files are by path in the Claude directory.
    """

    files: dict[str, _RecordedFile] = {}


def _read_state() -> _SyncState | None:
    """Return what claude-sync recorded of syncing, or None if not there or not understood."""
    try:
        return _SyncState.model_validate_json(
            (claude_sync_files_directory() / _STATE_FILE_NAME).read_text(
                encoding="utf-8"
            )
        )
    except OSError, ValidationError:
        return None


def is_first_pull() -> bool:
    """Return whether claude-sync has recorded nothing of syncing on this machine.

    If it is not sure, it is taken to be, because what follows is forcing the
    pull. If it is wrong the other way, claude-sync asks about overwriting files
    before its first pull, which does not work from a task.
    """
    state = _read_state()
    return state is None or not state.files


# claude-sync saves the remote version of a conflict beside the local file, as
# its name followed by this and when.
_CONFLICT_NAME = re.compile(r"(?P<original>.+)\.conflict\.\d{8}-\d{6}")


def _hash_file(path: pathlib.Path) -> str | None:
    """Return the hash that claude-sync records for the file at path, or None."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


@dataclasses.dataclass(frozen=True)
class _Conflict:
    """A conflict that claude-sync saved the remote version of, beside the local file."""

    # The remote version, and the local file, which may not exist.
    conflict_path: pathlib.Path
    original_path: pathlib.Path
    remote_hash: str
    local_hash: str | None


def _conflict_paths() -> list[pathlib.Path]:
    """Return the files named as conflicts, where claude-sync syncs."""
    paths: set[pathlib.Path] = set()
    for name in synced_paths():
        # A file in the Claude directory has its conflict beside it, and one in a
        # directory has it in there.
        paths.update(claude_directory().glob("{}.conflict.*".format(name)))
        paths.update((claude_directory() / name).rglob("*.conflict.*"))
    return sorted(paths)


def _conflicts() -> list[_Conflict]:
    """Return the conflicts that claude-sync has left, as it finds them."""
    found: list[_Conflict] = []
    for path in _conflict_paths():
        match = _CONFLICT_NAME.fullmatch(path.name)
        remote_hash = _hash_file(path) if match and path.is_file() else None
        if match is None or remote_hash is None:
            continue
        original_path = path.with_name(match["original"])
        found.append(
            _Conflict(
                conflict_path=path,
                original_path=original_path,
                remote_hash=remote_hash,
                local_hash=_hash_file(original_path),
            )
        )
    return found


def _relative_path(path: pathlib.Path) -> str:
    return path.relative_to(claude_directory()).as_posix()


def _clear_conflicts_with_own_uploads() -> list[pathlib.Path]:
    """Delete the conflicts that are only this machine's own earlier upload.

    A pull decides that the remote changed when its object is dated after the
    upload that claude-sync recorded, but the first is the storage's clock, to
    the second, and the other is this machine's. So if this machine's is behind,
    even by a fraction of a second, a file that it uploaded and has changed since
    looks changed on both sides. Then the remote version is the same as what
    claude-sync recorded having uploaded. See
    <https://github.com/tawanorg/claude-sync/issues/99>.

    Those are deleted, and nothing else is, including claude-sync's record. So
    the local file differs from the record, and the next push uploads it, which
    is not so if claude-sync keeps it (see _warn_if_kept_local). Returns the
    local files that were kept.
    """
    state = _read_state()
    if state is None:
        return []

    kept: list[pathlib.Path] = []
    for conflict in _conflicts():
        entry = state.files.get(_relative_path(conflict.original_path))
        if entry is None or entry.hash != conflict.remote_hash:
            continue
        try:
            conflict.conflict_path.unlink()
        except OSError:
            continue
        kept.append(conflict.original_path)
    return kept


def _keep_local_of_own_uploads() -> None:
    """Clear the conflicts that are only this machine's own earlier upload, and say so."""
    for path in _clear_conflicts_with_own_uploads():
        print(
            "Kept the local {}, as claude-sync's conflict with it was only this machine's own earlier upload.".format(
                _relative_path(path)
            )
        )


def _warn_if_kept_local(before: list[_Conflict]) -> None:
    """Warn about the conflicts that were resolved by keeping the local file.

    claude-sync then records the local file as uploaded, though it has not been,
    and a push only uploads a file that differs from what is recorded. So the
    bucket, and other machines, keep the remote version until the file next
    changes here. before is the conflicts from before they were resolved.
    """
    kept = [
        conflict
        for conflict in before
        if not conflict.conflict_path.exists()
        and conflict.local_hash is not None
        and conflict.local_hash != conflict.remote_hash
        and _hash_file(conflict.original_path) == conflict.local_hash
    ]
    if kept:
        print(
            "Kept the local version of {} file(s). claude-sync will not upload them until each next changes here, so other machines keep the remote version until then:".format(
                len(kept)
            )
        )
        for conflict in kept:
            print("  {}".format(_relative_path(conflict.original_path)))


class ClaudeSyncConfig(BaseModel):
    """Contents of the claude-sync config."""

    # A profile in the AWS config, with the credentials claude-sync signs in with.
    aws_profile: str
    bucket: str
    # A bucket of its own for the record of deleted sessions, which claude-sync
    # does not use. In the same region.
    deletions_bucket: str
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

        Keeping a local version, either way, is warned about, because
        claude-sync does not upload it (see _warn_if_kept_local).
        """
        resolve_args = ["conflicts"]
        if keep is not None:
            resolve_args.extend(["--keep", keep])
        before = _conflicts()
        result = command_run(
            command=self.binary_path,
            command_params=command_params,
            args=resolve_args,
        )
        _warn_if_kept_local(before)
        return result

    def push(self, *, command_params: CommandParams) -> Result:
        """Run `claude-sync push`, uploading local changes to cloud storage."""
        return command_run(
            command=self.binary_path,
            command_params=command_params,
            args=["push"],
        )

    def pull(
        self,
        *,
        command_params: CommandParams,
        dry_run: bool = False,
        force: bool = False,
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
        interactively. Except those that are only this machine's own earlier
        upload, which are not conflicts, and are cleared, unattended or not.

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
        # Those left from before, which the pull below may leave again.
        _keep_local_of_own_uploads()
        if unattended and self._conflicts_remain(command_params=hidden):
            raise ValueError("Not syncing, because conflicts are unresolved.")

        pull_result = self.pull(command_params=command_params)
        if _had_errors(command="pull", output=pull_result.stdout):
            raise ValueError("Not pushing, because the pull had errors.")
        if not _pull_finished(pull_result.stdout):
            raise ValueError("Not pushing, because the pull did not finish.")

        _keep_local_of_own_uploads()
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
        if _had_errors(command="push", output=push_result.stdout):
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
