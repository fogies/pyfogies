"""Facts about the installed pyfogies package itself."""

import importlib.metadata
import re

# importlib.metadata reports the PEP 440 canonical form, which is how Poetry
# normalizes the SemVer-hyphenated version string written in pyproject.toml
# and CHANGELOG.md (e.g. "0.0.0-dev.6" becomes "0.0.0.dev6"). These are the
# only two forms this project's own versions ever take.
_FINAL_RELEASE_RE = re.compile(r"^\d+\.\d+\.\d+$")
_DEV_RELEASE_RE = re.compile(r"^(?P<base>\d+\.\d+\.\d+)\.dev(?P<dev>\d+)$")


def pyfogies_version() -> str:
    """The installed pyfogies version, in this project's own format (e.g. "0.0.0-dev.6").

    Converts the PEP 440 form importlib.metadata reports back to the
    SemVer-hyphenated form used everywhere else in the project. Raises if
    the installed version doesn't match either expected shape, rather than
    guessing at an unfamiliar one.
    """
    installed_version = importlib.metadata.version("fogies")

    if _FINAL_RELEASE_RE.match(installed_version):
        return installed_version

    dev_release_match = _DEV_RELEASE_RE.match(installed_version)
    if dev_release_match:
        return "{}-dev.{}".format(
            dev_release_match.group("base"), dev_release_match.group("dev")
        )

    raise ValueError(
        "Unrecognized pyfogies version '{}'; expected 'X.Y.Z' or 'X.Y.Z.devN'".format(
            installed_version
        )
    )
