"""Test claude-sync is available, and is configured from the config."""

import pathlib
import subprocess

import pytest

from fogies.age_key import generate_age_key
from fogies.tools.aws_environ import AwsProfile
from fogies.tools.claude_sync import (
    _KEY_FILE_NAME,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import (
    _YAML_FILE_NAME,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import (
    _conflicts_remain,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import _had_errors  # pyright: ignore[reportPrivateUsage]
from fogies.tools.claude_sync import (
    _pull_finished,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import (
    claude_directory,
    claude_sync,
    claude_sync_files_directory,
    configure_claude_sync,
    is_first_pull,
    load_claude_sync_config,
    render_claude_sync_yaml,
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
region = "us-west-2"
scope = "sessions"
""".format(_AWS_PROFILE.name)
    if age_key is not None:
        text += 'age_key = "{}"\n'.format(age_key)
    _ = path.write_text(text, encoding="utf-8")
    return path


def test_claude_sync_is_available() -> None:
    """Context manager provides a working executable exposing the wrapped commands.

    Only checks --help, not push/pull/status themselves: those read
    ~/.claude-sync/config.yaml with no override, so any test exercising them
    would depend on this machine's ambient claude-sync setup rather than a
    controlled fixture.
    """
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


def test_configure_claude_sync_generates_a_key_when_the_config_has_none(
    tmp_path: pathlib.Path,
    claude_sync_files_dir: pathlib.Path,
    aws_config_path: pathlib.Path,
) -> None:
    claude_sync_config_path = _config_file(tmp_path)
    key_path = claude_sync_files_dir / _KEY_FILE_NAME
    yaml_path = claude_sync_files_dir / _YAML_FILE_NAME

    setup = configure_claude_sync(
        claude_sync_config_path=claude_sync_config_path,
        aws_config_path=aws_config_path,
        force=False,
    )

    # The key is saved in the config, for other machines, and is the one used.
    config = load_claude_sync_config(path=claude_sync_config_path)
    assert config.age_key is not None
    assert key_path.read_text(encoding="utf-8") == config.age_key + "\n"
    assert yaml_path.read_text(encoding="utf-8") == render_claude_sync_yaml(
        config, _AWS_PROFILE
    )
    assert setup.generated_age_key
    assert setup.applied_to_claude_sync_files


def test_configure_claude_sync_writes_the_files_when_the_key_is_already_in_the_config(
    tmp_path: pathlib.Path,
    claude_sync_files_dir: pathlib.Path,
    aws_config_path: pathlib.Path,
) -> None:
    claude_sync_config_path = _config_file(tmp_path, age_key=_KEY)
    key_path = claude_sync_files_dir / _KEY_FILE_NAME
    yaml_path = claude_sync_files_dir / _YAML_FILE_NAME

    setup = configure_claude_sync(
        claude_sync_config_path=claude_sync_config_path,
        aws_config_path=aws_config_path,
        force=False,
    )

    # The config's key is used, not replaced.
    assert load_claude_sync_config(path=claude_sync_config_path).age_key == _KEY
    assert key_path.read_text(encoding="utf-8") == _KEY + "\n"
    assert yaml_path.exists()
    assert not setup.generated_age_key
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


def test_claude_sync_conflicts_keeps_the_chosen_version(
    temp_home: pathlib.Path,
) -> None:
    """A conflict is resolved by keeping the remote version, which is saved beside it."""
    project_path = temp_home / ".claude" / "projects" / "demo"
    project_path.mkdir(parents=True)
    local_path = project_path / "a.jsonl"
    conflict_path = project_path / "a.jsonl.conflict.20260208-095132"
    _ = local_path.write_text("local", encoding="utf-8")
    _ = conflict_path.write_text("remote", encoding="utf-8")

    with claude_sync(
        binary_cache_path=STAGING_BINARY_CACHE_PATH, raise_if_env_exists=False
    ) as cs:
        _ = cs.resolve_conflicts(
            command_params=CommandParams(in_stream=False, hide=True), keep="remote"
        )

    assert local_path.read_text(encoding="utf-8") == "remote"
    assert not conflict_path.exists()


def test_claude_sync_list_conflicts_changes_nothing(temp_home: pathlib.Path) -> None:
    project_path = temp_home / ".claude" / "projects" / "demo"
    project_path.mkdir(parents=True)
    local_path = project_path / "a.jsonl"
    conflict_path = project_path / "a.jsonl.conflict.20260208-095132"
    _ = local_path.write_text("local", encoding="utf-8")
    _ = conflict_path.write_text("remote", encoding="utf-8")

    with claude_sync(
        binary_cache_path=STAGING_BINARY_CACHE_PATH, raise_if_env_exists=False
    ) as cs:
        result = cs.list_conflicts(
            command_params=CommandParams(in_stream=False, hide=True)
        )

    assert "a.jsonl" in result.stdout
    assert local_path.read_text(encoding="utf-8") == "local"
    assert conflict_path.read_text(encoding="utf-8") == "remote"


def test_had_errors() -> None:
    """Both a pull and a push print what failed, and still exit successfully."""
    assert not _had_errors("Pull complete: 2 downloaded")
    assert _had_errors("Pull complete: 1 failed\n\nErrors:\n  a.jsonl: timeout")
    assert _had_errors("Push complete: 1 failed\n\nErrors:\n  b.jsonl: timeout")


def test_pull_finished() -> None:
    # Every pull that runs to its end rebuilds the history, with nothing else
    # printed when there was nothing to download.
    assert _pull_finished(
        "\n".join(
            [
                "Fetching remote file list...",
                "  Rebuilt history.jsonl: 5 entries (5 existing + 0 recovered)",
            ]
        )
    )
    # A pull that was stopped, or did nothing, printed none of it.
    assert not _pull_finished("  Aborted.")
    assert not _pull_finished("Pull complete: 2 downloaded")
    assert not _pull_finished("")


def test_conflicts_remain() -> None:
    assert not _conflicts_remain("No conflicts found")
    assert _conflicts_remain("Found 1 conflict(s):")
    # What is not recognized is not taken to be none.
    assert _conflicts_remain("something else")


def test_is_first_pull(claude_sync_files_dir: pathlib.Path) -> None:
    """It is the first pull until claude-sync has recorded files, or if unsure."""
    assert is_first_pull()

    claude_sync_files_dir.mkdir()
    state_path = claude_sync_files_dir / "state.json"
    _ = state_path.write_text('{"files": {}}', encoding="utf-8")
    assert is_first_pull()

    _ = state_path.write_text("not json", encoding="utf-8")
    assert is_first_pull()

    _ = state_path.write_text('{"files": {"a.jsonl": {"hash": "x"}}}', encoding="utf-8")
    assert not is_first_pull()


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
