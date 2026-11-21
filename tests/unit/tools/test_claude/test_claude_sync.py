"""Test claude-sync is available, is configured from the config, and is synced.

That includes the conflicts that a sync can leave, and the output of claude-sync
that is read to know how a pull or a push went.
"""

import hashlib
import json
import pathlib
import subprocess
from collections.abc import Callable
from contextlib import nullcontext
from typing import Literal

import pytest
from invoke.runners import Result

from fogies.age_key import generate_age_key
from fogies.tools.aws_environ import AwsProfile
from fogies.tools.claude_sync import (
    _KEY_FILE_NAME,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import (
    _YAML_FILE_NAME,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import (
    _clear_conflicts_with_own_uploads,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import _conflicts  # pyright: ignore[reportPrivateUsage]
from fogies.tools.claude_sync import (
    _conflicts_remain,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import _had_errors  # pyright: ignore[reportPrivateUsage]
from fogies.tools.claude_sync import (
    _pull_finished,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import (
    _warn_if_kept_local,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import (
    ClaudeSyncConfig,
    claude_directory,
    claude_sync,
    claude_sync_claude_directory,
    claude_sync_files_directory,
    configure_claude_sync,
    is_first_pull,
    load_claude_sync_config,
    render_claude_sync_yaml,
    require_claude_sync_directory,
    update_claude_sync_config,
)
from fogies.tools.command import CommandParams
from tasks.paths import STAGING_BINARY_CACHE_PATH

# Any two different age secret keys will do.
_KEY = generate_age_key()
_OTHER_KEY = generate_age_key()

# The credentials claude-sync is configured with, with symbols in the secret
# that must survive being written.
_AWS_PROFILE = AwsProfile(
    name="claude-sync",
    aws_access_key_id="id",
    aws_secret_access_key="a/secret+with=symbols",
)


def _green(text: str) -> str:
    """Colour text as claude-sync does, which it does whatever it prints to."""
    return "\x1b[32m" + text + "\x1b[0m"


def _garbled(text: str) -> str:
    """Decode text as it is on Windows when the locale is not UTF-8.

    claude-sync prints UTF-8, and its symbols (e.g., a tick) come out as other
    characters, which is also how a pytest run on Windows sees them.
    """
    return text.encode("utf-8").decode("cp1252")


def _push_had_errors(output: str) -> bool:
    return _had_errors(command="push", output=output)


# What claude-sync prints, as of the version these forms are checked for.
_REBUILT = (
    "  "
    + _green(
        "Rebuilt history.jsonl: 5 entries (4 existing + 1 recovered from sessions)"
    )
    + "\n"
)

_PULL_WITH_A_CONFLICT_AND_AN_ERROR = "\n".join(
    [
        "\x1b[2m⋯\x1b[0m projects\\demo\r↓ [1/2] projects\\demo\\a.jsonl (1.2 KB)          ",
        "\r↓ [2/2] projects\\demo\\b.jsonl (3 B)          ",
        "\r\x1b[33m⚠\x1b[0m Conflict: projects\\demo\\c.jsonl (saved as .conflict)",
        # Printed by the syncer itself, in the middle of the progress.
        "Conflict detected: projects\\demo\\c.jsonl (keeping local, saving remote as .conflict)",
        "Warning: failed to restore mtime for projects\\demo\\a.jsonl: access denied",
        "\r\x1b[33m✗\x1b[0m projects\\demo\\d.jsonl: timeout",
        "",
        _green("✓") + " Pull complete: 2 downloaded, 1 conflicts, 1 failed",
        "",
        "\x1b[33mConflicts (both local and remote changed):\x1b[0m",
        "  \x1b[33m•\x1b[0m projects\\demo\\c.jsonl",
        "",
        "\x1b[2mLocal versions kept. Remote saved as .conflict files.\x1b[0m",
        "\x1b[2mRun '\x1b[36mclaude-sync conflicts\x1b[0m\x1b[2m' to review and resolve.\x1b[0m",
        "",
        "\x1b[33mErrors:\x1b[0m",
        "  \x1b[33m•\x1b[0m projects\\demo\\d.jsonl: timeout",
        "",
    ]
)

_PUSH_WITH_AN_ERROR = "\n".join(
    [
        "\r\x1b[36m↑\x1b[0m \x1b[2m[1/1]\x1b[0m projects\\demo\\a.jsonl (1.2 KB)          ",
        "\r\x1b[33m✗\x1b[0m [1/1] projects\\demo\\old.jsonl (deleted)          ",
        "\r\x1b[33m✗\x1b[0m projects\\demo\\b.jsonl: timeout",
        "",
        # Printed by the syncer itself.
        "Warning: failed to upload manifest: timeout",
        _green("✓")
        + " Push complete: \x1b[32m1 uploaded\x1b[0m, \x1b[33m1 deleted\x1b[0m, \x1b[33m1 failed\x1b[0m",
        "",
        "\x1b[33mErrors:\x1b[0m",
        "  \x1b[33m•\x1b[0m projects\\demo\\b.jsonl: timeout",
        "",
    ]
)


@pytest.fixture
def claude_sync_files_dir(temp_home: pathlib.Path) -> pathlib.Path:
    """Where claude-sync looks for its files, in the temporary home directory."""
    _ = temp_home
    return claude_sync_files_directory()


@pytest.fixture
def aws_config_path(tmp_path: pathlib.Path) -> pathlib.Path:
    """An AWS config with the profile that the config names."""
    path = tmp_path / "aws.toml"
    _ = path.write_text(
        """[{}]
aws_access_key_id = "{}"
aws_secret_access_key = "{}"
""".format(
            _AWS_PROFILE.name,
            _AWS_PROFILE.aws_access_key_id,
            _AWS_PROFILE.aws_secret_access_key,
        ),
        encoding="utf-8",
    )
    return path


def _config_file(tmp_path: pathlib.Path, *, age_key: str | None = None) -> pathlib.Path:
    """Write a config that names the profile in aws_config_path."""
    path = tmp_path / "claude-sync.toml"
    text = """
aws_profile = "{}"
bucket = "my-bucket"
deletions_bucket = "my-deletions-bucket"
region = "us-west-2"
scope = "sessions"
""".format(_AWS_PROFILE.name)
    if age_key is not None:
        text += 'age_key = "{}"\n'.format(age_key)
    _ = path.write_text(text, encoding="utf-8")
    return path


# What this machine uploaded, and the session as it is after it has grown.
_UPLOADED = b"What this machine uploaded."
_GROWN = b"What this machine uploaded. And what it has added since."


def _write_conflict(*, remote: bytes) -> tuple[pathlib.Path, pathlib.Path]:
    """Write a session that has grown, and the remote version saved beside it."""
    project = claude_directory() / "projects" / "demo"
    project.mkdir(parents=True)
    local = project / "a.jsonl"
    conflict = project / "a.jsonl.conflict.20261113-080344"
    _ = local.write_bytes(_GROWN)
    _ = conflict.write_bytes(remote)
    return local, conflict


def test_claude_directory_follows_claude_config_dir_but_claude_sync_does_not(
    temp_home: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Claude Code's directory is where it says, and claude-sync's is always ~/.claude."""
    assert claude_directory() == temp_home / ".claude"

    elsewhere = tmp_path / "elsewhere"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(elsewhere))

    assert claude_directory() == elsewhere
    assert claude_sync_claude_directory() == temp_home / ".claude"


def test_require_claude_sync_directory_refuses_only_where_they_differ(
    temp_home: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CLAUDE_CONFIG_DIR that is where claude-sync syncs anyway is not a problem."""
    require_claude_sync_directory()

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(temp_home / ".claude"))
    require_claude_sync_directory()

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "elsewhere"))
    with pytest.raises(ValueError, match="only syncs.*CLAUDE_CONFIG_DIR is set"):
        require_claude_sync_directory()


def test_claude_sync_refuses_before_building_if_the_claude_directory_is_elsewhere(
    temp_home: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No claude-sync command is run, or built to be run, that would sync another one."""
    _ = temp_home
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "elsewhere"))
    cache = tmp_path / "cache"

    with pytest.raises(ValueError, match="only syncs"):
        with claude_sync(binary_cache_path=cache, raise_if_env_exists=False):
            pass

    assert not cache.exists()


def test_claude_sync_is_available(temp_home: pathlib.Path) -> None:
    """Context manager provides a working executable exposing the wrapped commands.

    Only checks --help, not push/pull/status themselves: those read
    ~/.claude-sync/config.yaml with no override, so any test exercising them
    would depend on this machine's ambient claude-sync setup rather than a
    controlled fixture. (The home is replaced for the same reason, and so that
    CLAUDE_CONFIG_DIR, which claude_sync refuses, is not inherited.)
    """
    _ = temp_home
    with claude_sync(
        binary_cache_path=STAGING_BINARY_CACHE_PATH, raise_if_env_exists=False
    ) as cs:
        # Verify the executable exists.
        assert cs.binary_path.exists()

        # Run the executable and verify it exposes the commands this tool wraps.
        result = subprocess.run(
            [str(cs.binary_path), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "push" in result.stdout
        assert "pull" in result.stdout
        assert "status" in result.stdout


def test_claude_sync_accepts_the_files_that_configure_writes(
    tmp_path: pathlib.Path, temp_home: pathlib.Path, aws_config_path: pathlib.Path
) -> None:
    """claude-sync reads the config and key as written for it, without prompting.

    `status` only looks at local files, so this needs no bucket. A config or
    key claude-sync could not read would make it fail here. It looks for them
    in the home directory, which temp_home has replaced.
    """
    _ = temp_home
    _ = configure_claude_sync(
        claude_sync_config_path=_config_file(tmp_path),
        aws_config_path=aws_config_path,
        force=False,
    )

    with claude_sync(
        binary_cache_path=STAGING_BINARY_CACHE_PATH, raise_if_env_exists=False
    ) as cs:
        result = subprocess.run(
            [str(cs.binary_path), "status"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            stdin=subprocess.DEVNULL,
        )

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "config_age_key",
    [None, _KEY],
    ids=["config has no key", "config has a key"],
)
def test_configure_claude_sync_writes_the_files(
    tmp_path: pathlib.Path,
    claude_sync_files_dir: pathlib.Path,
    aws_config_path: pathlib.Path,
    config_age_key: str | None,
) -> None:
    """The config's key is used, or a new one is generated and saved in the config."""
    claude_sync_config_path = _config_file(tmp_path, age_key=config_age_key)
    key_path = claude_sync_files_dir / _KEY_FILE_NAME
    yaml_path = claude_sync_files_dir / _YAML_FILE_NAME

    setup = configure_claude_sync(
        claude_sync_config_path=claude_sync_config_path,
        aws_config_path=aws_config_path,
        force=False,
    )

    # The key that is used is in the config, for other machines.
    config = load_claude_sync_config(path=claude_sync_config_path)
    assert config.age_key is not None
    if config_age_key is not None:
        assert config.age_key == config_age_key
    assert key_path.read_text(encoding="utf-8") == config.age_key + "\n"
    assert yaml_path.read_text(encoding="utf-8") == render_claude_sync_yaml(
        config, _AWS_PROFILE
    )
    assert setup.generated_age_key is (config_age_key is None)
    assert setup.applied_to_claude_sync_files


def test_configure_claude_sync_needs_nothing_when_the_files_match(
    tmp_path: pathlib.Path, temp_home: pathlib.Path, aws_config_path: pathlib.Path
) -> None:
    _ = temp_home
    claude_sync_config_path = _config_file(tmp_path, age_key=_KEY)
    _ = configure_claude_sync(
        claude_sync_config_path=claude_sync_config_path,
        aws_config_path=aws_config_path,
        force=False,
    )

    setup = configure_claude_sync(
        claude_sync_config_path=claude_sync_config_path,
        aws_config_path=aws_config_path,
        force=False,
    )

    assert not setup.generated_age_key
    assert not setup.applied_to_claude_sync_files


@pytest.mark.parametrize(
    "config_age_key",
    [_KEY, None],
    ids=["config has a different key", "config has no key"],
)
def test_configure_claude_sync_refuses_a_different_key_and_changes_nothing(
    tmp_path: pathlib.Path,
    claude_sync_files_dir: pathlib.Path,
    aws_config_path: pathlib.Path,
    config_age_key: str | None,
) -> None:
    """With no key in the config, the one that would be generated cannot match."""
    claude_sync_config_path = _config_file(tmp_path, age_key=config_age_key)
    key_path = claude_sync_files_dir / _KEY_FILE_NAME
    yaml_path = claude_sync_files_dir / _YAML_FILE_NAME
    claude_sync_files_dir.mkdir()
    _ = key_path.write_text(_OTHER_KEY + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match"):
        _ = configure_claude_sync(
            claude_sync_config_path=claude_sync_config_path,
            aws_config_path=aws_config_path,
            force=False,
        )

    assert key_path.read_text(encoding="utf-8") == _OTHER_KEY + "\n"
    assert not yaml_path.exists()
    assert (
        load_claude_sync_config(path=claude_sync_config_path).age_key == config_age_key
    )


def test_configure_claude_sync_replaces_what_differs_when_forced(
    tmp_path: pathlib.Path,
    claude_sync_files_dir: pathlib.Path,
    aws_config_path: pathlib.Path,
) -> None:
    claude_sync_config_path = _config_file(tmp_path, age_key=_KEY)
    key_path = claude_sync_files_dir / _KEY_FILE_NAME
    yaml_path = claude_sync_files_dir / _YAML_FILE_NAME
    claude_sync_files_dir.mkdir()
    _ = key_path.write_text(_OTHER_KEY + "\n", encoding="utf-8")
    _ = yaml_path.write_text("something: else\n", encoding="utf-8")

    _ = configure_claude_sync(
        claude_sync_config_path=claude_sync_config_path,
        aws_config_path=aws_config_path,
        force=True,
    )

    assert key_path.read_text(encoding="utf-8") == _KEY + "\n"
    assert yaml_path.read_text(encoding="utf-8") == render_claude_sync_yaml(
        load_claude_sync_config(path=claude_sync_config_path), _AWS_PROFILE
    )


def test_update_claude_sync_config_updates_what_a_redirect_points_to(
    tmp_path: pathlib.Path,
) -> None:
    (tmp_path / "shared").mkdir()
    shared_path = _config_file(tmp_path / "shared")
    redirect_path = tmp_path / "project" / "claude-sync.toml"
    redirect_path.parent.mkdir()
    redirect_text = 'redirect = "../shared/claude-sync.toml"\n'
    _ = redirect_path.write_text(redirect_text, encoding="utf-8")

    update_claude_sync_config(path=redirect_path, age_key=_KEY)

    assert load_claude_sync_config(path=shared_path).age_key == _KEY
    assert redirect_path.read_text(encoding="utf-8") == redirect_text


@pytest.mark.parametrize("keep", ["remote", "local"])
def test_claude_sync_conflicts_keeps_the_chosen_version(
    temp_home: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    keep: Literal["local", "remote"],
) -> None:
    """A conflict is resolved by keeping a version, and keeping local is warned of."""
    _ = temp_home
    local_path, conflict_path = _write_conflict(remote=_UPLOADED)

    with claude_sync(
        binary_cache_path=STAGING_BINARY_CACHE_PATH, raise_if_env_exists=False
    ) as cs:
        _ = cs.resolve_conflicts(
            command_params=CommandParams(in_stream=False, hide=True), keep=keep
        )

    assert local_path.read_bytes() == (_GROWN if keep == "local" else _UPLOADED)
    assert not conflict_path.exists()
    assert ("projects/demo/a.jsonl" in capsys.readouterr().out) is (keep == "local")


@pytest.mark.parametrize("conflicted", [True, False], ids=["conflicts", "none"])
def test_claude_sync_list_conflicts_is_read_as_it_is_printed(
    temp_home: pathlib.Path, conflicted: bool
) -> None:
    """What it prints is what the parser reads, so this is checked against the
    real claude-sync, which only lists conflicts."""
    _ = temp_home
    paths = _write_conflict(remote=_UPLOADED) if conflicted else None
    claude_directory().mkdir(exist_ok=True)

    with claude_sync(
        binary_cache_path=STAGING_BINARY_CACHE_PATH, raise_if_env_exists=False
    ) as cs:
        result = cs.list_conflicts(
            command_params=CommandParams(in_stream=False, hide=True)
        )

    assert _conflicts_remain(result.stdout) is conflicted
    if paths:
        local_path, conflict_path = paths
        assert "a.jsonl" in result.stdout
        assert local_path.read_bytes() == _GROWN
        assert conflict_path.read_bytes() == _UPLOADED


@pytest.mark.parametrize(
    ("output", "errors", "finished"),
    [
        (_REBUILT, False, True),
        (_green("✓") + " Already up to date\n\n" + _REBUILT, False, True),
        (_PULL_WITH_A_CONFLICT_AND_AN_ERROR + _REBUILT, True, True),
        (_garbled(_PULL_WITH_A_CONFLICT_AND_AN_ERROR + _REBUILT), True, True),
        # A pull that downloaded, but did not go on to rebuild the history.
        (_green("✓") + " Pull complete: 2 downloaded\n", False, False),
    ],
    ids=[
        "nothing to download",
        "up to date",
        "conflict and error",
        "conflict and error, decoded as cp1252",
        "stopped",
    ],
)
def test_pull_output_is_understood(output: str, errors: bool, finished: bool) -> None:
    """A pull is understood from what it prints, as it exits successfully either way."""
    assert _had_errors(command="pull", output=output) is errors
    assert _pull_finished(output) is finished


@pytest.mark.parametrize(
    ("output", "errors"),
    [
        ("\r" + _green("✓") + " No changes to push\n\n", False),
        (_PUSH_WITH_AN_ERROR, True),
        (_garbled(_PUSH_WITH_AN_ERROR), True),
    ],
    ids=[
        "no changes",
        "uploads, a delete and an error",
        "uploads, a delete and an error, decoded as cp1252",
    ],
)
def test_push_output_is_understood(output: str, errors: bool) -> None:
    assert _had_errors(command="push", output=output) is errors


@pytest.mark.parametrize(
    ("understand", "output"),
    [
        # A summary, an errors heading, and a statement of how many conflicts
        # that are worded differently, as a new version of claude-sync might.
        (
            _pull_finished,
            _REBUILT + _green("✓") + " Pull finished: 2 downloaded\n",
        ),
        (
            _push_had_errors,
            _PUSH_WITH_AN_ERROR.replace("Errors:", "Problems:"),
        ),
        (_conflicts_remain, "There are 1 conflict(s):\n"),
    ],
    ids=["pull summary", "push errors heading", "conflicts count"],
)
def test_output_that_has_changed_is_not_recognised(
    understand: Callable[[str], object], output: str
) -> None:
    """A line that is not a form that was checked stops what is being done."""
    with pytest.raises(ValueError, match="not recognised"):
        _ = understand(output)


def test_is_first_pull(claude_sync_files_dir: pathlib.Path) -> None:
    """It is the first pull until claude-sync has recorded files."""
    assert is_first_pull()

    claude_sync_files_dir.mkdir()
    state_path = claude_sync_files_dir / "state.json"
    _ = state_path.write_text('{"files": {}}', encoding="utf-8")
    assert is_first_pull()

    _ = state_path.write_text('{"files": {"a.jsonl": {"hash": "x"}}}', encoding="utf-8")
    assert not is_first_pull()

    # A file recorded in some other form is still recorded, as being wrong the
    # other way forces a pull over what has been synced before.
    _ = state_path.write_text('{"files": {"a.jsonl": {}}}', encoding="utf-8")
    assert not is_first_pull()


@pytest.mark.parametrize("text", ["not json", '{"files": 5}', "[]"])
def test_is_first_pull_is_not_guessed_if_the_record_is_not_understood(
    claude_sync_files_dir: pathlib.Path, text: str
) -> None:
    """A record that is there but not understood is not taken to be none."""
    claude_sync_files_dir.mkdir()
    _ = (claude_sync_files_dir / "state.json").write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="not understood"):
        _ = is_first_pull()


def test_claude_sync_sync_unattended_requires_a_first_sync_to_be_attended(
    temp_home: pathlib.Path,
) -> None:
    """Nothing is run, or changed, for an unattended first sync."""
    _ = temp_home

    with claude_sync(
        binary_cache_path=STAGING_BINARY_CACHE_PATH, raise_if_env_exists=False
    ) as cs:
        with pytest.raises(ValueError, match="first sync"):
            cs.sync(command_params=CommandParams(in_stream=False), unattended=True)

    assert not claude_directory().exists()


@pytest.mark.parametrize(
    ("pull_output", "push_output", "calls", "error"),
    [
        (_REBUILT, "", ["pull", "after_pull", "push"], None),
        (
            _PULL_WITH_A_CONFLICT_AND_AN_ERROR + _REBUILT,
            "",
            ["pull"],
            "pull had errors",
        ),
        (
            _green("✓") + " Pull complete: 1 downloaded\n",
            "",
            ["pull"],
            "did not finish",
        ),
        ("Pull stopped\n", "", ["pull"], "not recognised"),
        # The push is not undone, so what it changed has been pushed by then.
        (
            _REBUILT,
            _PUSH_WITH_AN_ERROR,
            ["pull", "after_pull", "push"],
            "push had errors",
        ),
    ],
    ids=[
        "finished",
        "pull errors",
        "not finished",
        "not recognised",
        "push errors",
    ],
)
def test_claude_sync_sync_calls_after_pull_before_the_push(
    temp_home: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    pull_output: str,
    push_output: str,
    calls: list[str],
    error: str | None,
) -> None:
    """What it changes is pushed, and it is not run for a pull that failed."""
    _ = temp_home
    made: list[str] = []

    def fake_pull(**kwargs: object) -> Result:
        _ = kwargs
        made.append("pull")
        return Result(stdout=pull_output)

    def fake_push(**kwargs: object) -> Result:
        _ = kwargs
        made.append("push")
        return Result(stdout=push_output)

    def fake_conflicts_remain(**kwargs: object) -> bool:
        _ = kwargs
        return False

    monkeypatch.setattr("fogies.tools.claude_sync.is_first_pull", lambda: False)
    with claude_sync(
        binary_cache_path=STAGING_BINARY_CACHE_PATH, raise_if_env_exists=False
    ) as cs:
        monkeypatch.setattr(cs, "pull", fake_pull)
        monkeypatch.setattr(cs, "push", fake_push)
        monkeypatch.setattr(cs, "_conflicts_remain", fake_conflicts_remain)

        with pytest.raises(ValueError, match=error) if error else nullcontext():
            cs.sync(
                command_params=CommandParams(in_stream=False),
                unattended=True,
                after_pull=lambda: made.append("after_pull"),
            )

    assert made == calls


def _record_upload(name: str, content: bytes) -> pathlib.Path:
    """Write claude-sync's record of having uploaded a file with this content."""
    directory = claude_sync_files_directory()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "state.json"
    _ = path.write_text(
        json.dumps({"files": {name: {"hash": hashlib.sha256(content).hexdigest()}}}),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("recorded", "cleared"),
    [
        # The remote version is what this machine uploaded.
        (("projects/demo/a.jsonl", _UPLOADED), True),
        # Someone else changed it, or it is not known what was uploaded.
        (("projects/demo/a.jsonl", b"Something else."), False),
        (("projects/demo/other.jsonl", _UPLOADED), False),
        (None, False),
    ],
    ids=["own upload", "changed by another", "not recorded", "no record"],
)
def test_clear_conflicts_with_own_uploads(
    temp_home: pathlib.Path,
    recorded: tuple[str, bytes] | None,
    cleared: bool,
) -> None:
    """Only a conflict that is this machine's own upload goes, and nothing else."""
    _ = temp_home
    local, conflict = _write_conflict(remote=_UPLOADED)
    state = _record_upload(*recorded) if recorded else None
    state_before = state.read_bytes() if state else None

    assert _clear_conflicts_with_own_uploads() == ([local] if cleared else [])

    assert conflict.exists() is not cleared
    assert local.read_bytes() == _GROWN
    # claude-sync's record is left, so that the push uploads the local version.
    assert (state.read_bytes() if state else None) == state_before


def test_a_conflict_that_is_skipped_is_not_warned_about(
    temp_home: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A conflict still there was not kept local, whatever the resolver was asked.

    Keeping either version is checked, with the warning, against the real
    resolver in test_claude_sync_conflicts_keeps_the_chosen_version.
    """
    _ = temp_home
    _ = _write_conflict(remote=b"What another machine uploaded.")
    before = _conflicts()

    _warn_if_kept_local(before)

    assert capsys.readouterr().out == ""


def test_claude_sync_sync_clears_a_conflict_with_its_own_upload(
    temp_home: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unattended sync goes on through a conflict that is only its own upload."""
    _ = temp_home
    _ = _write_conflict(remote=_UPLOADED)
    _ = _record_upload("projects/demo/a.jsonl", _UPLOADED)
    made: list[str] = []

    def fake_pull(**kwargs: object) -> Result:
        _ = kwargs
        made.append("pull")
        return Result(stdout=_REBUILT)

    def fake_push(**kwargs: object) -> Result:
        _ = kwargs
        made.append("push")
        return Result(stdout="")

    def fake_conflicts_remain(**kwargs: object) -> bool:
        _ = kwargs
        return bool(_conflicts())

    monkeypatch.setattr("fogies.tools.claude_sync.is_first_pull", lambda: False)
    with claude_sync(
        binary_cache_path=STAGING_BINARY_CACHE_PATH, raise_if_env_exists=False
    ) as cs:
        monkeypatch.setattr(cs, "pull", fake_pull)
        monkeypatch.setattr(cs, "push", fake_push)
        monkeypatch.setattr(cs, "_conflicts_remain", fake_conflicts_remain)

        cs.sync(
            command_params=CommandParams(in_stream=False),
            unattended=True,
            after_pull=lambda: made.append("after_pull"),
        )

    assert made == ["pull", "after_pull", "push"]
    assert not _conflicts()


def test_claude_sync_sync_unattended_names_the_conflicts_that_stop_it(
    temp_home: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A conflict outside what is synced stops it, as claude-sync lists it, and is named.

    This is checked against the real claude-sync, as what it lists is what is named.
    """
    _ = temp_home
    stray = claude_directory() / "cache" / "c.json.conflict.20261113-080344"
    stray.parent.mkdir(parents=True)
    _ = stray.write_bytes(b"remote")
    made: list[str] = []

    def fake_pull(**kwargs: object) -> Result:
        _ = kwargs
        made.append("pull")
        return Result(stdout=_REBUILT)

    monkeypatch.setattr("fogies.tools.claude_sync.is_first_pull", lambda: False)
    with claude_sync(
        binary_cache_path=STAGING_BINARY_CACHE_PATH, raise_if_env_exists=False
    ) as cs:
        monkeypatch.setattr(cs, "pull", fake_pull)

        with pytest.raises(ValueError, match="Not syncing.*c\\.json"):
            cs.sync(command_params=CommandParams(in_stream=False), unattended=True)

    assert made == []
    assert stray.exists()


def _configure_scope(scope: Literal["full", "sessions"] | None) -> None:
    """Write claude-sync's config.yaml as configure does, for a scope, or none."""
    if scope is None:
        return
    config = ClaudeSyncConfig(
        aws_profile=_AWS_PROFILE.name,
        bucket="my-bucket",
        deletions_bucket="my-deletions-bucket",
        region="us-west-2",
        scope=scope,
    )
    directory = claude_sync_files_directory()
    directory.mkdir(parents=True, exist_ok=True)
    _ = (directory / _YAML_FILE_NAME).write_text(
        render_claude_sync_yaml(config, _AWS_PROFILE), encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("scope", "found"),
    [
        ("sessions", {"a.jsonl", "history.jsonl"}),
        ("full", {"a.jsonl", "history.jsonl", "p.json"}),
        # Which claude-sync takes as full.
        (None, {"a.jsonl", "history.jsonl", "p.json"}),
    ],
    ids=["sessions", "full", "no scope"],
)
def test_conflicts_are_looked_for_where_claude_sync_syncs(
    temp_home: pathlib.Path,
    scope: Literal["full", "sessions"] | None,
    found: set[str],
) -> None:
    """A conflict in a directory, or beside a file, is found if its scope syncs it."""
    _ = temp_home
    _configure_scope(scope)
    (claude_directory() / "projects" / "demo").mkdir(parents=True)
    (claude_directory() / "plugins").mkdir()
    for name in [
        "projects/demo/a.jsonl",
        "history.jsonl",
        "plugins/p.json",
        # Not synced in any scope.
        "cache/c.json",
    ]:
        path = claude_directory() / (name + ".conflict.20261113-080344")
        path.parent.mkdir(exist_ok=True)
        _ = path.write_bytes(b"remote")

    assert {c.original_path.name for c in _conflicts()} == found
