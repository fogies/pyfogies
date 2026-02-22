import io
import pathlib
import subprocess
import sys
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPResponse
from typing import cast, overload

from invoke.runners import Result

from fogies.tools.command import (
    CommandParams,
    ContextCommandParams,
    SubprocessCommandParams,
    command_run,
)

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

    @overload
    def init(
        self,
        *,
        command_params: SubprocessCommandParams,
        path_module: pathlib.Path,
    ) -> subprocess.CompletedProcess[str]: ...

    @overload
    def init(
        self,
        *,
        command_params: ContextCommandParams,
        path_module: pathlib.Path,
    ) -> Result: ...

    def init(
        self,
        *,
        command_params: CommandParams,
        path_module: pathlib.Path,
    ) -> subprocess.CompletedProcess[str] | Result:
        """Run terraform init.

        *path_module* is the folder containing the Terraform files (used as
        working directory). If *command_params* is ContextCommandParams, run via
        context.run(); otherwise use subprocess.run(). When using
        SubprocessCommandParams, set *capture_output* there to capture
        stdout/stderr as text. *command_params* is passed to context.run() or
        subprocess.run() as appropriate.
        """
        return command_run(
            command=self.path,
            command_params=command_params,
            args=["init", "-upgrade"],
            cwd=path_module,
        )

    @overload
    def apply(
        self,
        *,
        command_params: SubprocessCommandParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str]: ...

    @overload
    def apply(
        self,
        *,
        command_params: ContextCommandParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> Result: ...

    def apply(
        self,
        *,
        command_params: CommandParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str] | Result:
        """Run terraform apply.

        *path_module* is the folder containing the Terraform files (used as
        working directory). If *command_params* is ContextCommandParams, run via
        context.run(); otherwise use subprocess.run(). If *auto_approve* is
        true, pass -auto-approve. When using SubprocessCommandParams, set
        *capture_output* there to capture stdout/stderr as text. *command_params*
        is passed to context.run() or subprocess.run() as appropriate.
        """
        apply_args = ["apply"]
        if auto_approve:
            apply_args.append("-auto-approve")
        return command_run(
            command=self.path,
            command_params=command_params,
            args=apply_args,
            cwd=path_module,
        )

    @overload
    def destroy(
        self,
        *,
        command_params: SubprocessCommandParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str]: ...

    @overload
    def destroy(
        self,
        *,
        command_params: ContextCommandParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> Result: ...

    def destroy(
        self,
        *,
        command_params: CommandParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str] | Result:
        """Run terraform destroy.

        *path_module* is the folder containing the Terraform files (used as
        working directory). If *command_params* is ContextCommandParams, run via
        context.run(); otherwise use subprocess.run(). If *auto_approve* is
        true, pass -auto-approve. When using SubprocessCommandParams, set
        *capture_output* there to capture stdout/stderr as text. *command_params*
        is passed to context.run() or subprocess.run() as appropriate.
        """
        destroy_args = ["destroy"]
        if auto_approve:
            destroy_args.append("-auto-approve")
        return command_run(
            command=self.path,
            command_params=command_params,
            args=destroy_args,
            cwd=path_module,
        )


@contextmanager
def terraform(
    *,
    version: str = _DEFAULT_VERSION,
    path_binary_cache: pathlib.Path,
) -> Iterator[Terraform]:
    """Download a Terraform binary and yield a Terraform object.
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
    exe_path = path_binary_cache / exe_name

    if not exe_path.exists():
        path_binary_cache.mkdir(parents=True, exist_ok=True)

        url = _TERRAFORM_URL_TEMPLATE.format(version=version)
        response = cast(HTTPResponse, urllib.request.urlopen(url))
        with response:
            zip_bytes: bytes = response.read()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            _ = exe_path.write_bytes(zf.read("terraform.exe"))

    yield Terraform(version=version, path=exe_path)
