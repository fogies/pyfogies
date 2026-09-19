"""Tool for downloading a portable Go toolchain and using it to build/install Go programs."""

import io
import pathlib
import shutil
import sys
import urllib.request
import zipfile
from collections.abc import Generator
from contextlib import contextmanager
from http.client import HTTPResponse
from typing import cast

from invoke.runners import Result

from fogies.tools.command import CommandParams, command_run
from fogies.tools.environ import environ

# Most recent first; _KNOWN_VERSIONS[0] is the default.
_KNOWN_VERSIONS = [
    "1.27.1",
]

_DEFAULT_VERSION = _KNOWN_VERSIONS[0]

_GO_URL_TEMPLATE = "https://go.dev/dl/go{version}.windows-amd64.zip"


class _Go:
    """Represents a portable Go toolchain."""

    _version: str
    _root_path: pathlib.Path

    def __init__(self, *, version: str, root_path: pathlib.Path) -> None:
        self._version = version
        self._root_path = root_path

    @property
    def binary_version(self) -> str:
        """The Go toolchain version string."""
        return self._version

    @property
    def binary_path(self) -> pathlib.Path:
        """The path to the Go executable."""
        return self._root_path / "bin" / "go.exe"

    def install(
        self,
        *,
        command_params: CommandParams,
        module: str,
        gobin_path: pathlib.Path,
        raise_if_env_exists: bool,
    ) -> Result:
        """Run `go install <module>`, placing the built binary in gobin_path.

        *module* is a Go install target: an import path (optionally with an
        `@version` suffix), or a local directory. GOBIN is overridden for the
        duration of the call so the built binary lands in gobin_path, the one
        part of this call the caller actually needs to control. GOPATH/GOCACHE
        are Go's own module-download and build caches -- meant to be shared
        and reused across builds, not per-call scratch space -- so they live
        persistently under this Go installation's own version-specific
        directory (a sibling of its bin/), reused by every install() call
        made with this same toolchain rather than being rebuilt from a cold
        cache each time. raise_if_env_exists has no default; see
        fogies.tools.environ.environ() for why -- callers should almost
        always pass False, with True reserved for isolating a specific
        environment-related failure in this call.
        """
        gobin_path.mkdir(parents=True, exist_ok=True)
        gopath_path = self._root_path.parent / "gopath"
        gocache_path = self._root_path.parent / "gocache"
        gopath_path.mkdir(parents=True, exist_ok=True)
        gocache_path.mkdir(parents=True, exist_ok=True)
        with environ(
            {
                "GOBIN": str(gobin_path.resolve()),
                "GOPATH": str(gopath_path.resolve()),
                "GOCACHE": str(gocache_path.resolve()),
            },
            raise_if_env_exists=raise_if_env_exists,
        ):
            return command_run(
                command=self.binary_path,
                command_params=command_params,
                args=["install", module],
            )


@contextmanager
def go(
    *,
    version: str | None = None,
    binary_cache_path: pathlib.Path,
) -> Generator[_Go]:
    """Download a portable Go SDK and yield a handle to it.

    *version* when None uses the bundled default Go version.
    """
    if sys.platform != "win32":
        raise RuntimeError("Only implemented on Windows")

    if version is None:
        version = _DEFAULT_VERSION

    if version not in _KNOWN_VERSIONS:
        known = ", ".join(_KNOWN_VERSIONS)
        raise ValueError(
            "Unknown Go version '{}'; known versions: {}".format(version, known)
        )

    # The official zip's entries are all rooted under "go/"; account for that
    # directly rather than renaming after extraction.
    extract_path = binary_cache_path / "go_{}".format(version.replace(".", "_"))
    root_path = extract_path / "go"
    exe_path = root_path / "bin" / "go.exe"

    if not exe_path.exists():
        binary_cache_path.mkdir(parents=True, exist_ok=True)
        try:
            url = _GO_URL_TEMPLATE.format(version=version)
            response = cast(HTTPResponse, urllib.request.urlopen(url))
            with response:
                zip_bytes: bytes = response.read()

            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                zf.extractall(extract_path)
        except Exception:
            shutil.rmtree(extract_path, ignore_errors=True)
            raise

    if not exe_path.exists():
        raise RuntimeError("Go executable 'go.exe' not found in '{}'".format(root_path))

    yield _Go(version=version, root_path=root_path)
