import dataclasses
import io
import json
import pathlib
import sys
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPResponse
from typing import TypeVar, cast

from invoke.runners import Result
from pydantic import BaseModel, RootModel

from fogies.tools.command import CommandParams, command_run


@dataclasses.dataclass(frozen=True, slots=True)
class InitParams:
    """Params for terraform init."""

    upgrade: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class ApplyParams:
    """Params for terraform apply."""

    auto_approve: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class DestroyParams:
    """Params for terraform destroy."""

    auto_approve: bool = False


_KNOWN_VERSIONS = [
    "1.14.4",
]

_DEFAULT_VERSION = _KNOWN_VERSIONS[-1]

_TERRAFORM_URL_TEMPLATE = (
    "https://releases.hashicorp.com/terraform"
    "/{version}/terraform_{version}_windows_amd64.zip"
)

TerraformOutputModel = TypeVar("TerraformOutputModel", bound=BaseModel)


class _TerraformCommandOutputEntryModel(BaseModel):
    """One output entry from `terraform output -json`, wrapping a value."""

    value: object
    type: object
    sensitive: bool


class _TerraformCommandOutputModel(
    RootModel[dict[str, _TerraformCommandOutputEntryModel]],
):
    """Root model for the full `terraform output -json` payload."""


def _write_tfvars(
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
        raise ValueError("Path '{}' must end with '.tfvars.json'".format(path))
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
    _write_tfvars(path=path, variables=variables)
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
    def binary_version(self) -> str:
        """The Terraform binary version string."""
        return self._version

    @property
    def binary_path(self) -> pathlib.Path:
        """The path to the Terraform executable."""
        return self._path

    def init(
        self,
        *,
        command_params: CommandParams,
        module_path: pathlib.Path,
        init_params: InitParams | None = None,
    ) -> Result:
        """Run terraform init.

        *module_path* is the folder containing the Terraform files.
        *init_params.upgrade* when true passes -upgrade to terraform init.
        """
        command_params = command_params.require_cwd(module_path)
        if init_params is None:
            init_params = InitParams()
        init_args = ["init"]
        if init_params.upgrade:
            init_args.append("-upgrade")
        return command_run(
            command=self.binary_path,
            command_params=command_params,
            args=init_args,
        )

    def apply(
        self,
        *,
        command_params: CommandParams,
        module_path: pathlib.Path,
        tfvars_path: pathlib.Path | list[pathlib.Path] | None = None,
        apply_params: ApplyParams | None = None,
    ) -> Result:
        """Run terraform apply.

        *module_path* is the folder containing the Terraform files (used as
        working directory). If *apply_params.auto_approve* is true, pass
        -auto-approve. *tfvars_path* is optional; when set, pass -var-file for
        each path.
        """
        command_params = command_params.require_cwd(module_path)
        if apply_params is None:
            apply_params = ApplyParams()

        apply_args = ["apply"]
        if apply_params.auto_approve:
            apply_args.append("-auto-approve")
        if tfvars_path is not None:
            paths = (
                [tfvars_path]
                if isinstance(tfvars_path, pathlib.Path)
                else tfvars_path
            )
            for p in paths:
                apply_args.extend(["-var-file", str(p)])

        return command_run(
            command=self.binary_path,
            command_params=command_params,
            args=apply_args,
        )

    def destroy(
        self,
        *,
        command_params: CommandParams,
        module_path: pathlib.Path,
        tfvars_path: pathlib.Path | list[pathlib.Path] | None = None,
        destroy_params: DestroyParams | None = None,
    ) -> Result:
        """Run terraform destroy.

        *module_path* is the folder containing the Terraform files (used as
        working directory). If *destroy_params.auto_approve* is true, pass
        -auto-approve. *tfvars_path* is optional; when set, pass -var-file for
        each path.
        """
        command_params = command_params.require_cwd(module_path)
        if destroy_params is None:
            destroy_params = DestroyParams()

        destroy_args = ["destroy"]
        if destroy_params.auto_approve:
            destroy_args.append("-auto-approve")
        if tfvars_path is not None:
            paths = (
                [tfvars_path]
                if isinstance(tfvars_path, pathlib.Path)
                else tfvars_path
            )
            for p in paths:
                destroy_args.extend(["-var-file", str(p)])

        return command_run(
            command=self.binary_path,
            command_params=command_params,
            args=destroy_args,
        )

    def output(
        self,
        *,
        command_params: CommandParams,
        module_path: pathlib.Path,
        output_model: type[TerraformOutputModel],
    ) -> TerraformOutputModel:
        """Run terraform output -json and parse the result into a Pydantic model.

        *module_path* is the folder containing the Terraform files (used as
        working directory). *output_model* is the Pydantic BaseModel subclass
        used to validate the outputs. The JSON produced by
        `terraform output -json` is simplified to a mapping from output names
        to their `value` fields before validation.
        """
        command_params = command_params.require_cwd(module_path)
        result = command_run(
            command=self.binary_path,
            command_params=command_params,
            args=["output", "-json"],
        )

        parsed_terraform_output = _TerraformCommandOutputModel.model_validate_json(
            result.stdout
        )
        recovered_values = {
            name: entry.value for name, entry in parsed_terraform_output.root.items()
        }
        return output_model.model_validate(recovered_values)


@contextmanager
def terraform(
    *,
    version: str = _DEFAULT_VERSION,
    binary_cache_path: pathlib.Path,
    command_params: CommandParams | None = None,
    module_path: pathlib.Path | None = None,
    tfvars_path: pathlib.Path | list[pathlib.Path] | None = None,
    init_on_entry: bool = False,
    init_params: InitParams | None = None,
    apply_on_entry: bool = False,
    apply_params: ApplyParams | None = None,
    delete_on_exit: bool = False,
    destroy_params: DestroyParams | None = None,
) -> Iterator[Terraform]:
    """Download a Terraform binary and yield a Terraform object.

    If *init_on_entry* is true, run init after preparing the binary; requires
    *command_params* and *module_path*. If *apply_on_entry* is true, run
    apply after init; requires *command_params* and *module_path*.
    *tfvars_path* is optional for apply. If *delete_on_exit* is true, run
    destroy when exiting the context; requires *command_params* and
    *module_path*. *tfvars_path* is optional for destroy.
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

    if init_on_entry and (command_params is None or module_path is None):
        raise ValueError(
            "init_on_entry requires command_params and module_path"
        )
    if apply_on_entry and (command_params is None or module_path is None):
        raise ValueError(
            "apply_on_entry requires command_params and module_path"
        )
    if delete_on_exit and (command_params is None or module_path is None):
        raise ValueError(
            "delete_on_exit requires command_params and module_path"
        )

    exe_name = "terraform_{}.exe".format(version.replace(".", "_"))
    exe_path = binary_cache_path / exe_name

    if not exe_path.exists():
        binary_cache_path.mkdir(parents=True, exist_ok=True)

        url = _TERRAFORM_URL_TEMPLATE.format(version=version)
        response = cast(HTTPResponse, urllib.request.urlopen(url))
        with response:
            zip_bytes: bytes = response.read()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            _ = exe_path.write_bytes(zf.read("terraform.exe"))

    tf = Terraform(version=version, path=exe_path)

    if init_on_entry and command_params is not None and module_path is not None:
        init_result = tf.init(
            command_params=command_params,
            module_path=module_path,
            init_params=init_params,
        )
        if init_result.exited != 0:
            raise RuntimeError(
                "terraform init failed (exit {}): {}".format(
                    init_result.exited,
                    init_result.stderr.strip() or init_result.stdout.strip(),
                )
            )

    if (
        apply_on_entry
        and command_params is not None
        and module_path is not None
    ):
        apply_result = tf.apply(
            command_params=command_params,
            module_path=module_path,
            tfvars_path=tfvars_path,
            apply_params=apply_params,
        )
        if apply_result.exited != 0:
            raise RuntimeError(
                "terraform apply failed (exit {}): {}".format(
                    apply_result.exited,
                    apply_result.stderr.strip() or apply_result.stdout.strip(),
                )
            )

    try:
        yield tf
    finally:
        if (
            delete_on_exit
            and command_params is not None
            and module_path is not None
        ):
            destroy_result = tf.destroy(
                command_params=command_params,
                module_path=module_path,
                tfvars_path=tfvars_path,
                destroy_params=destroy_params,
            )
            if destroy_result.exited != 0:
                raise RuntimeError(
                    "terraform destroy failed (exit {}): {}".format(
                        destroy_result.exited,
                        destroy_result.stderr.strip()
                        or destroy_result.stdout.strip(),
                    )
                )
