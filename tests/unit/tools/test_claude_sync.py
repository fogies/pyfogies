"""Test claude-sync is available, and is configured from the config."""

import pathlib
import subprocess

import pytest

from fogies.age_key import generate_age_key
from fogies.tools.claude_sync import (
    _CONFIG_FILE_NAME,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import (
    _KEY_FILE_NAME,  # pyright: ignore[reportPrivateUsage]
)
from fogies.tools.claude_sync import (
    claude_sync,
    claude_sync_files_directory,
    configure_claude_sync,
    load_claude_sync_config,
    render_claude_sync_yaml,
)
from tasks.paths import STAGING_BINARY_CACHE_PATH

# Any valid age secret key will do; this one is fixed so that tests can compare it.
_KEY = "AGE-SECRET-KEY-1QQQSYQCYQ5RQWZQFPG9SCRGWPUGPZYSNZS23V9CCRYDPK8QARC0SWRYDWG"
_OTHER_KEY = generate_age_key()


@pytest.fixture
def temp_home(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Replace the home directory, where claude-sync looks for its files."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


@pytest.fixture
def claude_sync_files_dir(temp_home: pathlib.Path) -> pathlib.Path:
    """Where claude-sync looks for its files, in the temporary home directory."""
    _ = temp_home
    return claude_sync_files_directory()


def _secrets_file(
    tmp_path: pathlib.Path, *, age_key: str | None = None
) -> pathlib.Path:
    """Write a config, with symbols in the secret that must survive being written."""
    path = tmp_path / "claude-sync.toml"
    text = """
bucket = "my-bucket"
region = "us-west-2"
access_key_id = "id"
secret_access_key = "a/secret+with=symbols"
scope = "sessions"
"""
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
    tmp_path: pathlib.Path, temp_home: pathlib.Path
) -> None:
    """claude-sync reads the config and key as written for it, without prompting.

    `status` only looks at local files, so this needs no bucket. A config or
    key claude-sync could not read would make it fail here. It looks for them
    in the home directory, which temp_home has replaced.
    """
    _ = temp_home
    _ = configure_claude_sync(secrets_path=_secrets_file(tmp_path), force=False)

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
    tmp_path: pathlib.Path, claude_sync_files_dir: pathlib.Path
) -> None:
    secrets_path = _secrets_file(tmp_path)
    key_path = claude_sync_files_dir / _KEY_FILE_NAME
    config_path = claude_sync_files_dir / _CONFIG_FILE_NAME

    setup = configure_claude_sync(secrets_path=secrets_path, force=False)

    # The key is saved in the config, for other machines, and is the one used.
    config = load_claude_sync_config(path=secrets_path)
    assert config.age_key is not None
    assert key_path.read_text(encoding="utf-8") == config.age_key + "\n"
    assert config_path.read_text(encoding="utf-8") == render_claude_sync_yaml(config)
    assert setup.generated_age_key
    assert setup.applied_to_claude_sync_files


def test_configure_claude_sync_writes_the_files_when_the_key_is_already_in_the_config(
    tmp_path: pathlib.Path, claude_sync_files_dir: pathlib.Path
) -> None:
    secrets_path = _secrets_file(tmp_path, age_key=_KEY)
    key_path = claude_sync_files_dir / _KEY_FILE_NAME
    config_path = claude_sync_files_dir / _CONFIG_FILE_NAME

    setup = configure_claude_sync(secrets_path=secrets_path, force=False)

    # The config's key is used, not replaced.
    assert load_claude_sync_config(path=secrets_path).age_key == _KEY
    assert key_path.read_text(encoding="utf-8") == _KEY + "\n"
    assert config_path.exists()
    assert not setup.generated_age_key
    assert setup.applied_to_claude_sync_files


def test_configure_claude_sync_needs_nothing_when_the_files_match(
    tmp_path: pathlib.Path, temp_home: pathlib.Path
) -> None:
    _ = temp_home
    secrets_path = _secrets_file(tmp_path, age_key=_KEY)
    _ = configure_claude_sync(secrets_path=secrets_path, force=False)

    setup = configure_claude_sync(secrets_path=secrets_path, force=False)

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
    config_age_key: str | None,
) -> None:
    """With no key in the config, the one that would be generated cannot match."""
    secrets_path = _secrets_file(tmp_path, age_key=config_age_key)
    key_path = claude_sync_files_dir / _KEY_FILE_NAME
    config_path = claude_sync_files_dir / _CONFIG_FILE_NAME
    claude_sync_files_dir.mkdir()
    _ = key_path.write_text(_OTHER_KEY + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match"):
        _ = configure_claude_sync(secrets_path=secrets_path, force=False)

    assert key_path.read_text(encoding="utf-8") == _OTHER_KEY + "\n"
    assert not config_path.exists()
    assert load_claude_sync_config(path=secrets_path).age_key == config_age_key


def test_configure_claude_sync_replaces_what_differs_when_forced(
    tmp_path: pathlib.Path, claude_sync_files_dir: pathlib.Path
) -> None:
    secrets_path = _secrets_file(tmp_path, age_key=_KEY)
    key_path = claude_sync_files_dir / _KEY_FILE_NAME
    config_path = claude_sync_files_dir / _CONFIG_FILE_NAME
    claude_sync_files_dir.mkdir()
    _ = key_path.write_text(_OTHER_KEY + "\n", encoding="utf-8")
    _ = config_path.write_text("something: else\n", encoding="utf-8")

    _ = configure_claude_sync(secrets_path=secrets_path, force=True)

    assert key_path.read_text(encoding="utf-8") == _KEY + "\n"
    assert config_path.read_text(encoding="utf-8") == render_claude_sync_yaml(
        load_claude_sync_config(path=secrets_path)
    )
