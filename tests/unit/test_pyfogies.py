"""Unit tests for fogies.pyfogies."""

import pytest

from fogies.pyfogies import PyfogiesVersionFormat, pyfogies_version


@pytest.mark.parametrize(
    ("installed_version", "version_format", "expected_version"),
    [
        ("0.0.0.dev6", PyfogiesVersionFormat.PEP440, "0.0.0.dev6"),
        ("1.2.3", PyfogiesVersionFormat.PEP440, "1.2.3"),
        ("0.0.0.dev6", PyfogiesVersionFormat.SEMVER, "0.0.0-dev.6"),
        ("1.2.3", PyfogiesVersionFormat.SEMVER, "1.2.3"),
        ("0.0.0.dev6", PyfogiesVersionFormat.GIT_TAG, "v0.0.0-dev.6"),
        ("1.2.3", PyfogiesVersionFormat.GIT_TAG, "v1.2.3"),
    ],
)
def test_pyfogies_version_converts_to_format(
    monkeypatch: pytest.MonkeyPatch,
    installed_version: str,
    version_format: PyfogiesVersionFormat,
    expected_version: str,
) -> None:
    """importlib.metadata's PEP 440 form converts to the requested format."""

    def _version(_name: str) -> str:
        return installed_version

    monkeypatch.setattr("fogies.pyfogies.importlib.metadata.version", _version)

    assert pyfogies_version(version_format=version_format) == expected_version


@pytest.mark.parametrize(
    "installed_version",
    [
        "1.2.3.devfoo",  # dev suffix isn't a plain number
        "1.2.3rc1",  # a pre-release form, not a dev release
        "1.2.3.post1",  # a post-release form
        "1.2",  # incomplete, missing patch
    ],
)
@pytest.mark.parametrize("version_format", list(PyfogiesVersionFormat))
def test_pyfogies_version_raises_on_unrecognized_form(
    monkeypatch: pytest.MonkeyPatch,
    installed_version: str,
    version_format: PyfogiesVersionFormat,
) -> None:
    """A version in neither recognized form is not guessed at -- it raises."""

    def _version(_name: str) -> str:
        return installed_version

    monkeypatch.setattr("fogies.pyfogies.importlib.metadata.version", _version)

    with pytest.raises(ValueError, match="Unrecognized pyfogies version"):
        _ = pyfogies_version(version_format=version_format)
