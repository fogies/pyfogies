"""Test that the access-key-permissions module requires an account regional bucket namespace.

The module always denies creating an S3 bucket unless the request names the
account regional namespace. No mocks: creates a real, disposable IAM user,
applies the module against it, and confirms with a real AWS policy evaluation
(IAM's own SimulatePrincipalPolicy) which bucket creation is allowed.

The user is granted AWS's S3 full access policy, which allows creating a
bucket in any namespace, so the only thing that can deny it is the module's
own deny. A request that names no namespace is a request for the global
namespace.
"""

import pathlib

from pydantic import BaseModel

from fogies.boto_clients import boto_client_iam
from fogies.terraform.backend import BackendOutput
from fogies.tools.aws_environ import AwsEnviron, AwsProfile
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform,
    terraform_tfbackend,
    terraform_tfvars,
)
from tasks.paths import STAGING_BINARY_CACHE_PATH, TEST_BACKEND_STATUS_PATH
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PyfogiesTestBackendStates

_S3_FULL_ACCESS_POLICY_ARN = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
_CREATE_BUCKET_ACTION = "s3:CreateBucket"
_BUCKET_NAMESPACE_CONTEXT_KEY = "s3:x-amz-bucket-namespace"
_ACCOUNT_REGIONAL_NAMESPACE = "account-regional"


class _TestAccessKeyPermissionsBucketNamespaceVars(BaseModel):
    region: str
    username: str
    policies: list[str]


def test_access_key_permissions_bucket_namespace_requires_account_regional(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_aws_environ: AwsEnviron,
    pyfogies_test_backend: BackendOutput,
    access_key_username: str,
    access_key_profile: AwsProfile,
    tmp_path: pathlib.Path,
) -> None:
    """Creating a bucket is denied unless it is in the account regional namespace.

    The user is granted full S3 access, which allows creating a bucket in any
    namespace, so the only thing that can deny it is the module's own deny.
    A request that names no namespace is a request for the global namespace.
    """
    _ = access_key_profile  # dependency only: must exist first, and outlive this test.
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent
    tfbackend_path = tmp_path / "test-access-key-permissions.tfbackend"
    tfvars_path = tmp_path / "test-access-key-permissions.tfvars.json"

    backend_config = pyfogies_test_backend[
        PyfogiesTestBackendStates.TEST_ACCESS_KEY_PERMISSIONS
    ]

    with (
        terraform_tfbackend(
            path=tfbackend_path,
            backend_config=backend_config,
            aws_environ=pyfogies_test_aws_environ,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestAccessKeyPermissionsBucketNamespaceVars(
                region=pyfogies_test_config.aws.region,
                username=access_key_username,
                policies=[_S3_FULL_ACCESS_POLICY_ARN],
            ),
        ) as tfvars_path,
        terraform(
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
        ),
    ):
        iam = boto_client_iam()
        user_arn = iam.get_user(UserName=access_key_username)["User"]["Arn"]

        global_result = iam.simulate_principal_policy(
            PolicySourceArn=user_arn,
            ActionNames=[_CREATE_BUCKET_ACTION],
        )["EvaluationResults"][0]
        assert global_result["EvalDecision"] != "allowed"

        account_regional_result = iam.simulate_principal_policy(
            PolicySourceArn=user_arn,
            ActionNames=[_CREATE_BUCKET_ACTION],
            ContextEntries=[
                {
                    "ContextKeyName": _BUCKET_NAMESPACE_CONTEXT_KEY,
                    "ContextKeyValues": [_ACCOUNT_REGIONAL_NAMESPACE],
                    "ContextKeyType": "string",
                }
            ],
        )["EvaluationResults"][0]
        assert account_regional_result["EvalDecision"] == "allowed"
