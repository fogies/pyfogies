"""Test Terraform access-key-permissions module.

No mocks: creates a real, disposable IAM user, applies the module against
it, and confirms with a real AWS policy evaluation (IAM's own
SimulatePrincipalPolicy) that the granted permissions are allowed and
ungranted ones are denied. What matters is the resulting authorization
decision, not how the module wired it up internally.

The module grants permissions via statements (put in a managed policy the
module creates), via policies (attached managed policies), or both, so each
of those is applied and checked in turn, reusing one disposable user across
all of them. The statements grant is a few low-stakes read-only EC2
"describe" calls; the policies grant is AWS's S3 read-only policy. They cover
disjoint services, so a decision can only come from the grant that is
supposed to provide it.

SimulatePrincipalPolicy, not a live EC2 call, is deliberate: EC2's own
authorization cache for a newly attached policy was observed (via direct
experimentation) to lag by anywhere from under a second to well over a
minute, making a live-call-plus-retry approach unreliably slow to test
with. SimulatePrincipalPolicy evaluates the real, currently-attached
policy immediately and authoritatively, with no such propagation delay.
"""

from __future__ import annotations

import pathlib

import pytest
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

# The statements grant: related read-only actions in a single service.
_EC2_ACTIONS = [
    "ec2:DescribeAvailabilityZones",
    "ec2:DescribeRegions",
    "ec2:DescribeVpcs",
]

# The same service as the statements grant, but deliberately not granted by anything.
_UNGRANTED_ACTION = "ec2:DescribeInstances"

# The policies grant: AWS's own S3 read-only policy, and an action it allows.
# A different service from _EC2_ACTIONS, so the two grants stay distinguishable.
_MANAGED_POLICY_ARN = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
_MANAGED_ACTION = "s3:ListAllMyBuckets"


class _Statement(BaseModel):
    effect: str
    actions: list[str]
    resources: list[str]


class _Scenario(BaseModel):
    """One way of granting permissions, and what it should and shouldn't allow."""

    name: str
    policies: list[str]
    statements: list[_Statement]
    allowed: list[str]
    denied: list[str]


_EC2_STATEMENTS = [
    _Statement(effect="Allow", actions=_EC2_ACTIONS, resources=["*"]),
]

_SCENARIOS = [
    _Scenario(
        name="statements",
        policies=[],
        statements=_EC2_STATEMENTS,
        allowed=_EC2_ACTIONS,
        denied=[_UNGRANTED_ACTION, _MANAGED_ACTION],
    ),
    _Scenario(
        name="policies",
        policies=[_MANAGED_POLICY_ARN],
        statements=[],
        allowed=[_MANAGED_ACTION],
        denied=[*_EC2_ACTIONS, _UNGRANTED_ACTION],
    ),
    _Scenario(
        name="both",
        policies=[_MANAGED_POLICY_ARN],
        statements=_EC2_STATEMENTS,
        allowed=[*_EC2_ACTIONS, _MANAGED_ACTION],
        denied=[_UNGRANTED_ACTION],
    ),
]


class _TestAccessKeyPermissionsVars(BaseModel):
    region: str
    username: str
    policies: list[str]
    statements: list[_Statement]


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=[s.name for s in _SCENARIOS])
def test_access_key_permissions_grants_and_restricts(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_aws_environ: AwsEnviron,
    pyfogies_test_backend: BackendOutput,
    access_key_username: str,
    access_key_profile: AwsProfile,
    scenario: _Scenario,
    tmp_path: pathlib.Path,
) -> None:
    """Every action the scenario grants is allowed; every other one is not.

    One IAM user for the whole module, reused across scenarios; each
    scenario applies the module against it, checks the result, then
    destroys before the next one applies.
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
            variables=_TestAccessKeyPermissionsVars(
                region=pyfogies_test_config.aws.region,
                username=access_key_username,
                policies=scenario.policies,
                statements=scenario.statements,
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

        results = iam.simulate_principal_policy(
            PolicySourceArn=user_arn,
            ActionNames=[*scenario.allowed, *scenario.denied],
        )["EvaluationResults"]
        decisions = {r["EvalActionName"]: r["EvalDecision"] for r in results}

        for action in scenario.allowed:
            assert decisions[action] == "allowed", action
        for action in scenario.denied:
            assert decisions[action] != "allowed", action
