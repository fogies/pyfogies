"""Unit tests for fogies.pyfogies."""

import pytest

from fogies.pyfogies import pyfogies_version


@pytest.mark.parametrize(
    ("installed_version", "expected_version"),
    [
        ("0.0.0.dev6", "0.0.0-dev.6"),
        ("1.2.3", "1.2.3"),
    ],
)
def test_pyfogies_version_converts_to_project_format(
    monkeypatch: pytest.MonkeyPatch,
    installed_version: str,
    expected_version: str,
) -> None:
    """importlib.metadata's PEP 440 form converts to this project's SemVer-hyphenated form."""

    def _version(_name: str) -> str:
        return installed_version

    monkeypatch.setattr("fogies.pyfogies.importlib.metadata.version", _version)

    assert pyfogies_version() == expected_version


@pytest.mark.parametrize(
    "installed_version",
    [
        "1.2.3.devfoo",  # dev suffix isn't a plain number
        "1.2.3rc1",  # a pre-release form, not a dev release
        "1.2.3.post1",  # a post-release form
        "1.2",  # incomplete, missing patch
    ],
)
def test_pyfogies_version_raises_on_unrecognized_form(
    monkeypatch: pytest.MonkeyPatch,
    installed_version: str,
) -> None:
    """A version in neither recognized form is not guessed at -- it raises."""

    def _version(_name: str) -> str:
        return installed_version

    monkeypatch.setattr("fogies.pyfogies.importlib.metadata.version", _version)

    with pytest.raises(ValueError, match="Unrecognized pyfogies version"):
        _ = pyfogies_version()
