import io
import json
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
from pydantic import BaseModel

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


def write_tfvars(
    *,
    path: pathlib.Path,
    variables: BaseModel,
) -> None:
    """Write Terraform variables to a .tfvars.json file.

    *path* is the output file path (use a .tfvars.json suffix so Terraform
    accepts it with -var-file). *variables* is a Pydantic model; its fields
    are written as the Terraform variable set (nested models are serialized).
    """
    suffixes = path.suffixes
    if suffixes[-2:] != [".tfvars", ".json"]:
        raise ValueError(
            "Path '{}' must end with '.tfvars.json'".format(
                path
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(variables.model_dump(mode="json"), f, indent=2)


@contextmanager
def terraform_tfvars(
    *,
    path: pathlib.Path,
    variables: BaseModel,
    delete_on_exit: bool = False,
) -> Iterator[pathlib.Path]:
    """Write in-memory variables to a file and yield the path for use with apply/destroy.

    *path* is where the .tfvars.json file is written. *variables* must be a
    Pydantic model; its fields are written as the Terraform variable set.
    Yields *path* so the caller can pass it as the tfvars argument to apply()
    or destroy(). If *delete_on_exit* is true, remove the file when exiting the
    context.
    """
    write_tfvars(path=path, variables=variables)
    try:
        yield path
    finally:
        if delete_on_exit and path.exists():
            path.unlink()


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
        module_path: pathlib.Path,
    ) -> subprocess.CompletedProcess[str]: ...

    @overload
    def init(
        self,
        *,
        command_params: ContextCommandParams,
        module_path: pathlib.Path,
    ) -> Result: ...

    def init(
        self,
        *,
        command_params: CommandParams,
        module_path: pathlib.Path,
    ) -> subprocess.CompletedProcess[str] | Result:
        """Run terraform init.

        *module_path* is the folder containing the Terraform files (used as
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
            cwd=module_path,
        )

    @overload
    def apply(
        self,
        *,
        command_params: SubprocessCommandParams,
        module_path: pathlib.Path,
        tfvars_path: pathlib.Path | list[pathlib.Path],
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str]: ...

    @overload
    def apply(
        self,
        *,
        command_params: ContextCommandParams,
        module_path: pathlib.Path,
        tfvars_path: pathlib.Path | list[pathlib.Path],
        auto_approve: bool = False,
    ) -> Result: ...

    def apply(
        self,
        *,
        command_params: CommandParams,
        module_path: pathlib.Path,
        tfvars_path: pathlib.Path | list[pathlib.Path],
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str] | Result:
        """Run terraform apply.

        *module_path* is the folder containing the Terraform files (used as
        working directory). If *command_params* is ContextCommandParams, run via
        context.run(); otherwise use subprocess.run(). If *auto_approve* is
        true, pass -auto-approve. When using SubprocessCommandParams, set
        *capture_output* there to capture stdout/stderr as text. *command_params*
        is passed to context.run() or subprocess.run() as appropriate. *tfvars_path* is
        the path or a list of paths to .tfvars files; pass -var-file for each.
        """
        apply_args = ["apply"]
        if auto_approve:
            apply_args.append("-auto-approve")
        paths = [tfvars_path] if isinstance(tfvars_path, pathlib.Path) else tfvars_path
        for p in paths:
            apply_args.extend(["-var-file", str(p)])
        return command_run(
            command=self.path,
            command_params=command_params,
            args=apply_args,
            cwd=module_path,
        )

    @overload
    def destroy(
        self,
        *,
        command_params: SubprocessCommandParams,
        module_path: pathlib.Path,
        tfvars_path: pathlib.Path | list[pathlib.Path],
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str]: ...

    @overload
    def destroy(
        self,
        *,
        command_params: ContextCommandParams,
        module_path: pathlib.Path,
        tfvars_path: pathlib.Path | list[pathlib.Path],
        auto_approve: bool = False,
    ) -> Result: ...

    def destroy(
        self,
        *,
        command_params: CommandParams,
        module_path: pathlib.Path,
        tfvars_path: pathlib.Path | list[pathlib.Path],
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str] | Result:
        """Run terraform destroy.

        *module_path* is the folder containing the Terraform files (used as
        working directory). If *command_params* is ContextCommandParams, run via
        context.run(); otherwise use subprocess.run(). If *auto_approve* is
        true, pass -auto-approve. When using SubprocessCommandParams, set
        *capture_output* there to capture stdout/stderr as text. *command_params*
        is passed to context.run() or subprocess.run() as appropriate. *tfvars_path* is
        the path or a list of paths to .tfvars files; pass -var-file for each.
        """
        destroy_args = ["destroy"]
        if auto_approve:
            destroy_args.append("-auto-approve")
        paths = [tfvars_path] if isinstance(tfvars_path, pathlib.Path) else tfvars_path
        for p in paths:
            destroy_args.extend(["-var-file", str(p)])
        return command_run(
            command=self.path,
            command_params=command_params,
            args=destroy_args,
            cwd=module_path,
        )


@contextmanager
def terraform(
    *,
    version: str = _DEFAULT_VERSION,
    path_binary_cache: pathlib.Path,
) -> Iterator[Terraform]:
    """Download a Terraform binary and yield a Terraform object."""
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
