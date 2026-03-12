import dataclasses
import io
import pathlib
import sys
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPResponse
from typing import cast

_KNOWN_VERSIONS = [
    "0.17.7",
]

_DEFAULT_VERSION = _KNOWN_VERSIONS[-1]

_OLLAMA_URL_TEMPLATE = (
    "https://github.com/ollama/ollama/releases/download"
    "/v{version}/ollama-windows-amd64.zip"
)


@dataclasses.dataclass(frozen=True, slots=True)
class Ollama:
    """Represents an Ollama CLI binary."""

    _version: str
    _path: pathlib.Path

    @property
    def binary_version(self) -> str:
        """The Ollama binary version string."""
        return self._version

    @property
    def binary_path(self) -> pathlib.Path:
        """The path to the Ollama executable."""
        return self._path


@contextmanager
def ollama(
    *,
    version: str = _DEFAULT_VERSION,
    binary_cache_path: pathlib.Path,
) -> Iterator[Ollama]:
    """Download an Ollama Windows CLI release and yield an Ollama object.

    *version* is the Ollama release tag version (e.g., "0.17.7"). The archive is
    downloaded from the GitHub releases page if it does not already exist in
    *binary_cache_path*. The CLI zip archive `ollama-windows-amd64.zip` is
    fetched and the full folder structure is extracted into a versioned
    directory inside *binary_cache_path* and used from there.
    """
    if sys.platform != "win32":
        raise RuntimeError("Only implemented on Windows")

    if version not in _KNOWN_VERSIONS:
        known = ", ".join(_KNOWN_VERSIONS)
        raise ValueError(
            "Unknown Ollama version '{}'; known versions: {}".format(
                version,
                known,
            )
        )

    dir_name = "ollama_{}".format(version.replace(".", "_"))
    version_dir = binary_cache_path / dir_name

    if not version_dir.exists():
        version_dir.mkdir(parents=True, exist_ok=True)

        url = _OLLAMA_URL_TEMPLATE.format(version=version)
        response = cast(HTTPResponse, urllib.request.urlopen(url))
        with response:
            zip_bytes: bytes = response.read()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(version_dir)

    exe_path = version_dir / "ollama.exe"
    if not exe_path.exists():
        raise RuntimeError(
            "Ollama executable 'ollama.exe' not found in '{}'".format(version_dir)
        )

    try:
        yield Ollama(version, exe_path)
    finally:
        # No teardown is required for the Ollama CLI binary.
        pass
