"""Test the package version in pyproject.toml is a valid semantic version."""
from pathlib import Path
import tomllib

import pytest
import semver


def test_package_version_is_valid_semver(pytestconfig: pytest.Config):
    """Test the package version in pyproject.toml is a valid semantic version."""
    # Use pytest rootdir to find pyproject.toml.
    pyproject_path = Path(pytestconfig.rootdir, "pyproject.toml")
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    
    version = pyproject["project"]["version"]
    
    # Validate using semver package, will raise ValueError if invalid.
    semver.VersionInfo.parse(version)
