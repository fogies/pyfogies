"""Fixtures for the pyfogies-test-backend Terraform module."""

import json
import pathlib
from collections.abc import Iterator
from typing import cast

import boto3
import pytest
from fogies_paths import PATH_STAGING_BINARY_CACHE
from mypy_boto3_s3.type_defs import ObjectIdentifierTypeDef
from pydantic import BaseModel

from fogies.terraform.backend import BackendOutput, BackendVars
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from fogies.tools.aws_environ import AwsEnviron
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfvars,
)
from tests.terraform.backend import (
    PYFOGIES_TEST_TERRAFORM_BACKEND_NAME,
    PYFOGIES_TEST_TERRAFORM_BACKEND_STATES,
)


class _PyFogiesTestBackendOutput(BaseModel):
    backend: BackendOutput


def _verify_backend_states_destroyed(backend: BackendOutput) -> None:
    """Verify each state in the bucket is empty, then delete bucket contents so Terraform can destroy it."""

    # If any bucket still has something in it, we cannot delete the bucket.
    # Obtain a client to iterate through the state buckets.
    client = boto3.client("s3", region_name=backend.region)
    for state_name, state_key in backend.state_keys.items():
        # Obtain the current state of the key.
        try:
            response = client.get_object(Bucket=backend.bucket_name, Key=state_key)
        except client.exceptions.NoSuchKey:
            continue  # State key not present; nothing to verify.

        # Access the state JSON to determine if there are any resources.
        body = response["Body"].read().decode()
        state_json = cast(dict[str, object], json.loads(body))
        resources = cast(list[object], state_json.get("resources", []))

        if len(resources) > 0:
            msg = (
                "In fixture teardown, state '{}' still has {} resource(s).\n{}".format(
                    state_name,
                    len(resources),
                    json.dumps(resources, indent=2),
                )
            )
            pytest.fail(msg)

    # Delete only state keys that we verified (and their lock files).
    state_keys = set(backend.state_keys.values())
    lock_keys = {"{}.tflock".format(key) for key in state_keys}
    keys_to_delete = state_keys | lock_keys

    # Bucket has versioning enabled; delete all versions and delete markers.
    objects_to_delete: list[ObjectIdentifierTypeDef] = []
    paginator = client.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=backend.bucket_name):
        for version in page.get("Versions") or []:
            key = version.get("Key")
            version_id = version.get("VersionId")
            if key in keys_to_delete and version_id is not None:
                objects_to_delete.append({"Key": key, "VersionId": version_id})
        for marker in page.get("DeleteMarkers") or []:
            key = marker.get("Key")
            version_id = marker.get("VersionId")
            if key in keys_to_delete and version_id is not None:
                objects_to_delete.append({"Key": key, "VersionId": version_id})

    # Perform the deletions.
    for i in range(0, len(objects_to_delete), 1000):
        _ = client.delete_objects(
            Bucket=backend.bucket_name,
            Delete={"Objects": objects_to_delete[i : i + 1000]},
        )


@pytest.fixture(scope="session")
def pyfogies_test_backend(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_aws_environ: AwsEnviron,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[BackendOutput]:
    """Apply the backend module; yield output; destroy on teardown."""
    _ = pyfogies_test_aws_environ
    command_params = CommandParams(in_stream=False)
    backend_module_path = pathlib.Path(__file__).resolve().parent
    tmp_path = tmp_path_factory.mktemp("pyfogies-test-backend")
    tfvars_path = tmp_path / "pyfogies-test-backend.tfvars.json"

    with (
        terraform_tfvars(
            path=tfvars_path,
            variables=BackendVars(
                name=PYFOGIES_TEST_TERRAFORM_BACKEND_NAME,
                region=pyfogies_test_config.aws.region,
                states=[s.value for s in PYFOGIES_TEST_TERRAFORM_BACKEND_STATES],
                # force_destroy is intentionally false to require explicit cleanup of resources.
                # Every test module should destroy its own resources.
                # This fixture confirms that before destroying their states.
                # This ensures we do not orphan resources by deleting the state that captures their creation.
                force_destroy=False,
            ),
        ) as tfvars_path,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=backend_module_path,
            tfvars_path=tfvars_path,
            init_on_entry=True,
            init_params=InitParams(
                upgrade=True,
                reconfigure=True,
            ),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            delete_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_PyFogiesTestBackendOutput,
        ) as output,
    ):
        try:
            yield output.backend
        finally:
            # Verify that backend states are empty, then delete bucket contents so Terraform can destroy it.
            _verify_backend_states_destroyed(output.backend)
