"""Facts about the installed pyfogies package itself."""

import importlib.metadata
import re
from enum import StrEnum

# importlib.metadata reports the PEP 440 canonical form, which is how Poetry
# normalizes the SemVer-hyphenated version string written in pyproject.toml
# and CHANGELOG.md (e.g. "0.0.0-dev.6" becomes "0.0.0.dev6"). These are the
# only two shapes this project's own versions ever take.
_FINAL_RELEASE_RE = re.compile(r"^\d+\.\d+\.\d+$")
_DEV_RELEASE_RE = re.compile(r"^(?P<base>\d+\.\d+\.\d+)\.dev(?P<dev>\d+)$")


class PyfogiesVersionFormat(StrEnum):
    """The formats in which pyfogies_version() can return the installed version."""

    # As importlib.metadata reports it, e.g. "0.0.0.dev6".
    PEP440 = "pep440"
    # As written in pyproject.toml and CHANGELOG.md, e.g. "0.0.0-dev.6".
    SEMVER = "semver"
    # The release tag for the version, e.g. "v0.0.0-dev.6".
    GIT_TAG = "git_tag"


def _pep440_version() -> str:
    """The installed pyfogies version, as PEP 440 (e.g. "0.0.0.dev6").

    Raises if the installed version doesn't match either expected shape,
    rather than guessing at an unfamiliar one.
    """
    installed_version = importlib.metadata.version("fogies")

    if _FINAL_RELEASE_RE.match(installed_version) or _DEV_RELEASE_RE.match(
        installed_version
    ):
        return installed_version

    raise ValueError(
        "Unrecognized pyfogies version '{}'; expected 'X.Y.Z' or 'X.Y.Z.devN'".format(
            installed_version
        )
    )


def _semver_version() -> str:
    """The installed pyfogies version, as SemVer (e.g. "0.0.0-dev.6")."""
    pep440_version = _pep440_version()

    dev_release_match = _DEV_RELEASE_RE.match(pep440_version)
    if dev_release_match:
        return "{}-dev.{}".format(
            dev_release_match.group("base"), dev_release_match.group("dev")
        )

    return pep440_version


def pyfogies_version(*, version_format: PyfogiesVersionFormat) -> str:
    """The installed pyfogies version, in the requested *version_format*."""
    match PyfogiesVersionFormat(version_format):
        case PyfogiesVersionFormat.PEP440:
            return _pep440_version()
        case PyfogiesVersionFormat.SEMVER:
            return _semver_version()
        case PyfogiesVersionFormat.GIT_TAG:
            return "v{}".format(_semver_version())
