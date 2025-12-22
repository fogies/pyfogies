"""Test the package version in pyproject.toml is a valid semantic version."""

import tomllib
from pathlib import Path
from typing import cast

import pytest
import semver


def test_package_version_is_valid_semver(pytestconfig: pytest.Config):
    """Test the package version in pyproject.toml is a valid semantic version."""
    # Use pytest rootdir to find pyproject.toml.
    pyproject_path = Path(pytestconfig.rootpath, "pyproject.toml")
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    version: str = cast(str, pyproject["project"]["version"])

    # Validate using semver package, will raise ValueError if invalid.
    _ = semver.VersionInfo.parse(version)
