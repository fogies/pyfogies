"""Session-scoped ALB fixtures shared across test modules."""

import pathlib
from collections.abc import Iterator

import pytest
import requests
from pydantic import BaseModel

from fogies.ready_poll import (
    READY_POLL_EXCEPTIONS_HTTP,
    READY_POLL_TIMING_LONG,
    ready_poll,
)
from fogies.terraform.alb import AlbOutput
from fogies.terraform.backend import BackendOutput
from fogies.terraform.network import NetworkOutput
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfbackend,
    terraform_tfvars,
)
from tasks.paths import PATH_STAGING_BINARY_CACHE, PATH_TEST_BACKEND_STATUS
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PyfogiesTestTerraformBackendStates

_TEST_ALB_NAME_SELF_SIGNED = "pyfogies-test-alb-self-signed"
_TEST_ALB_MODULE = pathlib.Path(__file__).parent / "test_alb_self_signed"


class PyfogiesTestAlbOutput(BaseModel):
    alb: AlbOutput
    alb_security_group_id: str


class _AlbSelfSignedVars(BaseModel):
    region: str
    alb_name: str
    vpc_id: str
    subnet_ids: list[str]


class _TfAlbSelfSignedOutput(BaseModel):
    alb: AlbOutput
    alb_security_group_id: str


def _wait_for_alb(dns_name: str) -> None:
    for attempt in ready_poll(
        exceptions=READY_POLL_EXCEPTIONS_HTTP, timing=READY_POLL_TIMING_LONG
    ):
        with attempt:
            _ = requests.get(
                "http://{}".format(dns_name), timeout=5, allow_redirects=False
            )


@pytest.fixture(scope="session")
def pyfogies_test_alb_self_signed(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_backend: BackendOutput,
    pyfogies_test_network: NetworkOutput,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[PyfogiesTestAlbOutput]:
    """Session-scoped self-signed ALB. Shared by ALB tests and other test modules."""
    command_params = CommandParams(in_stream=False)
    module_path = _TEST_ALB_MODULE
    tmp_path = tmp_path_factory.mktemp("pyfogies-test-alb-self-signed")
    tfbackend_path = tmp_path / "pyfogies-test-alb-self-signed.tfbackend"
    tfvars_path = tmp_path / "pyfogies-test-alb-self-signed.tfvars.json"
    backend = pyfogies_test_backend[
        PyfogiesTestTerraformBackendStates.TEST_ALB_SELF_SIGNED.value
    ]

    with (
        terraform_tfbackend(
            path=tfbackend_path,
            backend=backend,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_AlbSelfSignedVars(
                region=pyfogies_test_config.aws.region,
                alb_name=_TEST_ALB_NAME_SELF_SIGNED,
                vpc_id=pyfogies_test_network.vpc_id,
                subnet_ids=list(pyfogies_test_network.subnet_ids),
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
            output_model=_TfAlbSelfSignedOutput,
        ) as tf_output,
    ):
        _wait_for_alb(tf_output.alb.alb_dns_name)
        yield PyfogiesTestAlbOutput(
            alb=tf_output.alb,
            alb_security_group_id=tf_output.alb_security_group_id,
        )
