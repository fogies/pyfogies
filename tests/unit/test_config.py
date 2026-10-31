"""Test loading config files, including those that redirect to a shared config."""

import pathlib

import pytest
from pydantic import BaseModel

from fogies.config import load_config, resolve_config_path


class _Config(BaseModel):
    name: str


def _write(path: pathlib.Path, text: str) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(text, encoding="utf-8")
    return path


def test_load_config_reads_the_model(tmp_path: pathlib.Path) -> None:
    path = _write(tmp_path / "config.toml", 'name = "plain"\n')

    config = load_config(path=path, model=_Config, template_factory=lambda: "")

    assert config == _Config(name="plain")


def test_load_config_follows_a_redirect(tmp_path: pathlib.Path) -> None:
    _ = _write(tmp_path / "shared" / "config.toml", 'name = "shared"\n')
    path = _write(
        tmp_path / "project" / "secrets" / "config.toml",
        'redirect = "../../shared/config.toml"\n',
    )

    config = load_config(path=path, model=_Config, template_factory=lambda: "")

    assert config == _Config(name="shared")


def test_resolve_config_path_is_where_a_write_belongs(tmp_path: pathlib.Path) -> None:
    shared = _write(tmp_path / "shared" / "config.toml", 'name = "shared"\n')
    redirect = _write(
        tmp_path / "project" / "config.toml", 'redirect = "../shared/config.toml"\n'
    )
    plain = _write(tmp_path / "plain.toml", 'name = "plain"\n')

    assert resolve_config_path(path=redirect).resolve() == shared.resolve()
    assert resolve_config_path(path=plain) == plain


@pytest.mark.parametrize(
    ("redirect_text", "error", "match"),
    [
        ('redirect = "a.toml"\nname = "x"\n', ValueError, "only that"),
        ("redirect = 1\n", ValueError, "only that"),
        ('redirect = "missing.toml"\n', FileNotFoundError, "was not found"),
        ('redirect = "chain.toml"\n', ValueError, "itself a redirect"),
    ],
    ids=["other keys", "not a path", "missing target", "chained"],
)
def test_load_config_rejects_a_bad_redirect(
    tmp_path: pathlib.Path, redirect_text: str, error: type[Exception], match: str
) -> None:
    _ = _write(tmp_path / "chain.toml", 'redirect = "a.toml"\n')
    _ = _write(tmp_path / "a.toml", 'name = "a"\n')
    path = _write(tmp_path / "config.toml", redirect_text)

    with pytest.raises(error, match=match):
        _ = load_config(path=path, model=_Config, template_factory=lambda: "")


def test_load_config_rejects_a_path_that_is_not_toml(tmp_path: pathlib.Path) -> None:
    """It is rejected before the template would create a file with that name."""
    path = tmp_path / "config.json"

    with pytest.raises(ValueError, match=r"config\.json.*\.toml extension"):
        _ = load_config(path=path, model=_Config, template_factory=lambda: "")

    assert not path.exists()


def test_a_redirect_to_a_file_that_is_not_toml_is_rejected(
    tmp_path: pathlib.Path,
) -> None:
    _ = _write(tmp_path / "shared.json", 'name = "shared"\n')
    path = _write(tmp_path / "config.toml", 'redirect = "shared.json"\n')

    with pytest.raises(ValueError, match=r"shared\.json.*\.toml extension"):
        _ = load_config(path=path, model=_Config, template_factory=lambda: "")
    with pytest.raises(ValueError, match=r"shared\.json.*\.toml extension"):
        _ = resolve_config_path(path=path)
