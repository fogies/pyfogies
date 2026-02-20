import io
import pathlib
import sys
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPResponse
from typing import cast

_BIN_DIR = pathlib.Path(".bin")

_KNOWN_VERSIONS = [
    "1.14.4",
]

_DEFAULT_VERSION = _KNOWN_VERSIONS[-1]

_TERRAFORM_URL_TEMPLATE = (
    "https://releases.hashicorp.com/terraform"
    "/{version}/terraform_{version}_windows_amd64.zip"
)


class Terraform:
    """Represents a Terraform binary."""

    _version: str
    _path: pathlib.Path

    def __init__(self, *, version: str, path: pathlib.Path) -> None:
        self._version = version
        self._path = path

    @property
    def version(self) -> str:
        """The Terraform version string."""
        return self._version

    @property
    def path(self) -> pathlib.Path:
        """The path to the Terraform executable."""
        return self._path


@contextmanager
def terraform(
    *,
    version: str = _DEFAULT_VERSION,
    cache_dir: pathlib.Path = _BIN_DIR,
) -> Iterator[Terraform]:
    """Download a Terraform binary and yield a Terraform object.

    Cache the downloaded binary in *cache_dir* (defaulting to ``.bin``).

    """
    if sys.platform != "win32":
        raise RuntimeError("Only implemented on Windows")

    if version not in _KNOWN_VERSIONS:
        known = ", ".join(_KNOWN_VERSIONS)
        raise ValueError(
            "Unknown Terraform version '{}'; known versions: {}".format(
                version,
                known,
            )
        )

    exe_name = "terraform_{}.exe".format(version.replace(".", "_"))
    exe_path = cache_dir / exe_name

    if not exe_path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)

        url = _TERRAFORM_URL_TEMPLATE.format(version=version)
        response = cast(HTTPResponse, urllib.request.urlopen(url))
        with response:
            zip_bytes: bytes = response.read()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            _ = exe_path.write_bytes(zf.read("terraform.exe"))

    yield Terraform(version=version, path=exe_path)
