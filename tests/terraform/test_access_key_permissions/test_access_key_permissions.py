"""Test Terraform access-key-permissions module.

No mocks: creates a real, disposable IAM user, applies the module against
it with a few related low-stakes permissions (read-only EC2 "describe"
calls), and confirms with a real AWS policy evaluation (IAM's own
SimulatePrincipalPolicy) that the granted permissions are allowed and a
related but ungranted one is denied.

SimulatePrincipalPolicy, not a live EC2 call, is deliberate: EC2's own
authorization cache for a newly attached policy was observed (via direct
experimentation) to lag by anywhere from under a second to well over a
minute, making a live-call-plus-retry approach unreliably slow to test
with. SimulatePrincipalPolicy evaluates the real, currently-attached
policy immediately and authoritatively, with no such propagation delay.
"""

from __future__ import annotations

import pathlib
import uuid
from collections.abc import Iterator

import pytest
from pydantic import BaseModel

import fogies.aws_access_key as aws_access_key
from fogies.terraform.access_key_permissions import AccessKeyPermissionsOutput
from fogies.terraform.backend import BackendOutput
from fogies.tools.aws_environ import AwsEnviron, AwsProfile
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfbackend,
    terraform_tfvars,
)
from fogies.typing import boto_client_iam
from tasks.paths import PATH_STAGING_BINARY_CACHE, PATH_TEST_BACKEND_STATUS
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PyfogiesTestTerraformBackendStates

# Shared by the access_key_username fixture below and by
# _delete_stale_access_key_users, which sweeps by this prefix since it
# can't know a prior run's exact suffix.
_USERNAME_PREFIX = "pyfogies-test-access-key-permissions-"

# Mirrors the actions granted in main.tf's access_key_permissions module.
_GRANTED_ACTIONS = [
    "ec2:DescribeAvailabilityZones",
    "ec2:DescribeRegions",
    "ec2:DescribeVpcs",
]

# Related to the granted actions (same service), but deliberately not granted.
_UNGRANTED_ACTION = "ec2:DescribeInstances"


class _TestVars(BaseModel):
    region: str
    username: str


class _TestOutput(BaseModel):
    access_key_permissions: AccessKeyPermissionsOutput


def _delete_user_and_keys(
    *, username: str, protected_key_id: str, protected_username: str
) -> None:
    """Delete username and all its keys, if it exists.

    protected_key_id/protected_username guard the currently-authenticated
    admin key/user, so a coincidental name collision can never delete them.
    """
    try:
        keys = aws_access_key.get_keys(username=username)
    except ValueError:
        return
    for key in (keys.current, keys.previous):
        if key is not None:
            aws_access_key.delete_key(
                username=username,
                key_id=key.key_id,
                protected_key_ids={protected_key_id},
            )
    aws_access_key.delete_user(
        username=username, protected_usernames={protected_username}
    )


def _delete_stale_access_key_users(
    *, protected_key_id: str, protected_username: str
) -> None:
    """Delete any leftover test users from prior runs that crashed before cleanup.

    username is unique per run, so an exact-name check would never find a
    prior run's leftover -- sweep by the shared prefix instead.
    """
    for user in aws_access_key.list_users():
        if user.username.startswith(_USERNAME_PREFIX):
            _delete_user_and_keys(
                username=user.username,
                protected_key_id=protected_key_id,
                protected_username=protected_username,
            )


@pytest.fixture(scope="module")
def access_key_username() -> str:
    """A fresh, never-before-used username for this test run.

    Unique per run: some AWS-side authorization caching appears to key on
    the ARN string rather than the user's underlying unique ID, so
    recreating the same name repeatedly (as happens across many local test
    runs) can leave a stale "no policy" result that blocks a fresh grant
    for an unpredictably long time.
    """
    return _USERNAME_PREFIX + uuid.uuid4().hex[:8]


@pytest.fixture(scope="module")
def access_key_user(
    access_key_username: str, pyfogies_test_aws_environ: AwsEnviron
) -> Iterator[AwsProfile]:
    """Create a disposable IAM user with an access key; delete both on teardown.

    Sweeps up any leftover users from prior runs that crashed before
    cleanup, since those would sit under a different run's suffix forever
    otherwise.
    """
    _delete_stale_access_key_users(
        protected_key_id=pyfogies_test_aws_environ.aws_access_key_id,
        protected_username=pyfogies_test_aws_environ.username,
    )
    profile = aws_access_key.create_user(username=access_key_username)
    try:
        yield profile
    finally:
        _delete_user_and_keys(
            username=access_key_username,
            protected_key_id=pyfogies_test_aws_environ.aws_access_key_id,
            protected_username=pyfogies_test_aws_environ.username,
        )


@pytest.fixture(scope="module")
def access_key_permissions_output(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_backend: BackendOutput,
    access_key_username: str,
    access_key_user: AwsProfile,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[_TestOutput]:
    """Apply the access-key-permissions module for access_key_user; yield output; destroy on teardown."""
    _ = access_key_user  # dependency only: must exist first, and outlive this fixture.
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent
    tmp_path = tmp_path_factory.mktemp("test-access-key-permissions")
    tfbackend_path = tmp_path / "test-access-key-permissions.tfbackend"
    tfvars_path = tmp_path / "test-access-key-permissions.tfvars.json"

    backend = pyfogies_test_backend[
        PyfogiesTestTerraformBackendStates.TEST_ACCESS_KEY_PERMISSIONS.value
    ]

    with (
        terraform_tfbackend(
            path=tfbackend_path,
            backend=backend,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestVars(
                region=pyfogies_test_config.aws.region, username=access_key_username
            ),
        ) as tfvars_path,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=module_path,
            tfvars_path=tfvars_path,
            tfbackend_path=tfbackend_path,
            backend=backend,
            backend_status_path=PATH_TEST_BACKEND_STATUS,
            init_on_entry=True,
            init_params=InitParams(upgrade=True, reconfigure=True),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestOutput,
        ) as output,
    ):
        yield output


def test_access_key_permissions_output(
    access_key_username: str,
    access_key_permissions_output: _TestOutput,
) -> None:
    """Applying the module outputs the granted user's name and policy."""
    output = access_key_permissions_output.access_key_permissions
    assert output.username == access_key_username
    policy = output.policy
    assert len(policy.statements) == 1
    statement = policy.statements[0]
    assert statement.effect == "Allow"
    assert statement.resources == ["*"]
    # aws_iam_policy_document does not preserve declaration order for actions.
    assert set(statement.actions) == set(_GRANTED_ACTIONS)


def test_access_key_permissions_grants_and_restricts(
    access_key_username: str,
    access_key_permissions_output: _TestOutput,
) -> None:
    """Every granted permission is allowed; a related but ungranted one is denied.

    access_key_user isn't referenced directly here (SimulatePrincipalPolicy
    only needs the username), but access_key_permissions_output already
    depends on it, so it exists and outlives this test regardless.
    """
    _ = access_key_permissions_output
    iam = boto_client_iam()
    user_arn = iam.get_user(UserName=access_key_username)["User"]["Arn"]

    results = iam.simulate_principal_policy(
        PolicySourceArn=user_arn,
        ActionNames=[*_GRANTED_ACTIONS, _UNGRANTED_ACTION],
    )["EvaluationResults"]
    decisions = {r["EvalActionName"]: r["EvalDecision"] for r in results}

    for action in _GRANTED_ACTIONS:
        assert decisions[action] == "allowed", action
    assert decisions[_UNGRANTED_ACTION] != "allowed"
