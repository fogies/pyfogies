import dataclasses
import io
import pathlib
import subprocess
import sys
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPResponse
from typing import assert_never, overload, cast

from invoke.context import Context
from invoke.runners import Result

_KNOWN_VERSIONS = [
    "1.14.4",
]

_DEFAULT_VERSION = _KNOWN_VERSIONS[-1]

_TERRAFORM_URL_TEMPLATE = (
    "https://releases.hashicorp.com/terraform"
    "/{version}/terraform_{version}_windows_amd64.zip"
)


@dataclasses.dataclass
class ContextRunParams:
    """Params for execution via invoke context.run()."""

    context: Context


@dataclasses.dataclass
class SubprocessRunParams:
    """Params for execution via subprocess.run()."""

    capture_output: bool = False


RunParams = ContextRunParams | SubprocessRunParams


def _run_command(
    *,
    run_params: RunParams,
    command_args: list[str],
    cwd: pathlib.Path | None,
) -> subprocess.CompletedProcess[str] | Result:
    """Run a command via context.run() or subprocess.run().
    """
    if isinstance(run_params, ContextRunParams):
        # invoke's context.run() returns None when run with disown=True.
        # Ensure future revisions to this code never introduce that parameter.
        if cwd is not None:
            with run_params.context.cd(str(cwd)):  # pyright: ignore[reportUnknownMemberType]
                result = run_params.context.run(" ".join(command_args))
        else:
            result = run_params.context.run(" ".join(command_args))
        return cast(Result, result)
    elif isinstance(run_params, SubprocessRunParams):  # pyright: ignore[reportUnnecessaryIsInstance]
        return subprocess.run(
            command_args,
            capture_output=run_params.capture_output,
            text=True if run_params.capture_output else None,
            cwd=cwd,
        )
    else:
        assert_never(run_params)


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
        run_params: SubprocessRunParams,
        path_module: pathlib.Path,
    ) -> subprocess.CompletedProcess[str]: ...

    @overload
    def init(
        self,
        *,
        run_params: ContextRunParams,
        path_module: pathlib.Path,
    ) -> Result: ...

    def init(
        self,
        *,
        run_params: RunParams,
        path_module: pathlib.Path,
    ) -> subprocess.CompletedProcess[str] | Result:
        """Run terraform init.

        *path_module* is the folder containing the Terraform files (used as
        working directory). If *run_params* is ContextRunParams, run via
        context.run(); otherwise use subprocess.run(). When using
        SubprocessRunParams, set *capture_output* there to capture
        stdout/stderr as text. *run_params* is passed to context.run() or
        subprocess.run() as appropriate.
        """
        command_args = [str(self.path), "init", "-upgrade"]
        return _run_command(
            run_params=run_params,
            command_args=command_args,
            cwd=path_module,
        )

    @overload
    def apply(
        self,
        *,
        run_params: SubprocessRunParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str]: ...

    @overload
    def apply(
        self,
        *,
        run_params: ContextRunParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> Result: ...

    def apply(
        self,
        *,
        run_params: RunParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str] | Result:
        """Run terraform apply.

        *path_module* is the folder containing the Terraform files (used as
        working directory). If *run_params* is ContextRunParams, run via
        context.run(); otherwise use subprocess.run(). If *auto_approve* is
        true, pass -auto-approve. When using SubprocessRunParams, set
        *capture_output* there to capture stdout/stderr as text. *run_params*
        is passed to context.run() or subprocess.run() as appropriate.
        """
        command_args = [str(self.path), "apply"]
        if auto_approve:
            command_args.append("-auto-approve")
        return _run_command(
            run_params=run_params,
            command_args=command_args,
            cwd=path_module,
        )

    @overload
    def destroy(
        self,
        *,
        run_params: SubprocessRunParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str]: ...

    @overload
    def destroy(
        self,
        *,
        run_params: ContextRunParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> Result: ...

    def destroy(
        self,
        *,
        run_params: RunParams,
        path_module: pathlib.Path,
        auto_approve: bool = False,
    ) -> subprocess.CompletedProcess[str] | Result:
        """Run terraform destroy.

        *path_module* is the folder containing the Terraform files (used as
        working directory). If *run_params* is ContextRunParams, run via
        context.run(); otherwise use subprocess.run(). If *auto_approve* is
        true, pass -auto-approve. When using SubprocessRunParams, set
        *capture_output* there to capture stdout/stderr as text. *run_params*
        is passed to context.run() or subprocess.run() as appropriate.
        """
        command_args = [str(self.path), "destroy"]
        if auto_approve:
            command_args.append("-auto-approve")
        return _run_command(
            run_params=run_params,
            command_args=command_args,
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
