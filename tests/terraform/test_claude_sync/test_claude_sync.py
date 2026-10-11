"""Test Terraform claude-sync module.

Applies the module for real and checks what it created: the bucket, in the
account regional namespace and with versioning, and the IAM user. Does not
exercise claude-sync itself, or the permissions granted to the user; those are
the access-key-permissions module's tests.
"""

import pathlib

from pydantic import BaseModel

from fogies.boto_clients import boto_client_iam, boto_client_s3
from fogies.terraform.backend import BackendOutput
from fogies.tools.aws_environ import AwsEnviron
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfbackend,
    terraform_tfvars,
)
from tasks.paths import STAGING_BINARY_CACHE_PATH, TEST_BACKEND_STATUS_PATH
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PyfogiesTestBackendStates

_TEST_CLAUDE_SYNC_NAME = "pyfogies-test-claude-sync"
_TEST_CLAUDE_SYNC_TAGS = {"Project": "pyfogies-test-claude-sync"}


class _TestClaudeSyncVars(BaseModel):
    region: str
    name: str
    tags: dict[str, str] = {}


class _TestClaudeSyncOutput(BaseModel):
    bucket: str
    region: str
    user_name: str


def test_claude_sync_creates_bucket_and_user(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_aws_environ: AwsEnviron,
    pyfogies_test_backend: BackendOutput,
    tmp_path: pathlib.Path,
) -> None:
    """The module creates a versioned account regional bucket and an IAM user."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent
    tfbackend_path = tmp_path / "test-claude-sync.tfbackend"
    tfvars_path = tmp_path / "test-claude-sync.tfvars.json"

    backend_config = pyfogies_test_backend[PyfogiesTestBackendStates.TEST_CLAUDE_SYNC]
    region = pyfogies_test_config.aws.region

    with (
        terraform_tfbackend(
            path=tfbackend_path,
            backend_config=backend_config,
            aws_environ=pyfogies_test_aws_environ,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestClaudeSyncVars(
                region=region,
                name=_TEST_CLAUDE_SYNC_NAME,
                tags=_TEST_CLAUDE_SYNC_TAGS,
            ),
        ) as tfvars_path,
        terraform_output(
            binary_cache_path=STAGING_BINARY_CACHE_PATH,
            command_params=command_params,
            module_path=module_path,
            tfvars_path=tfvars_path,
            tfbackend_path=tfbackend_path,
            backend_config=backend_config,
            aws_environ=pyfogies_test_aws_environ,
            backend_status_path=TEST_BACKEND_STATUS_PATH,
            init_on_entry=True,
            init_params=InitParams(upgrade=True, reconfigure=True),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestClaudeSyncOutput,
        ) as output,
    ):
        assert output.region == region
        assert output.user_name == _TEST_CLAUDE_SYNC_NAME
        # The account regional namespace requires the account ID and region.
        assert output.bucket == "{}-{}-{}-an".format(
            _TEST_CLAUDE_SYNC_NAME, pyfogies_test_aws_environ.account_id, region
        )

        versioning = boto_client_s3(region=region).get_bucket_versioning(
            Bucket=output.bucket
        )
        assert versioning.get("Status") == "Enabled"

        user = boto_client_iam().get_user(UserName=output.user_name)
        assert user["User"]["UserName"] == _TEST_CLAUDE_SYNC_NAME
