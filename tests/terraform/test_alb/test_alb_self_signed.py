"""Test Terraform ALB module with a self-signed certificate."""

import pathlib
import time
from collections.abc import Iterator

import pytest
import requests
import requests.exceptions
from pydantic import BaseModel

from fogies.terraform.alb import AlbOutput
from fogies.terraform.backend import BackendOutput
from fogies.terraform.network import NetworkOutput
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfbackend_s3,
    terraform_tfvars,
)
from tasks.paths import PATH_STAGING_BINARY_CACHE
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PYFOGIES_TEST_TERRAFORM_BACKEND_STATES

_TEST_ALB_NAME = "pyfogies-test-alb"


class _TestAlbVars(BaseModel):
    region: str
    alb_name: str


class _TestAlbOutput(BaseModel):
    network: NetworkOutput
    alb: AlbOutput


@pytest.fixture(scope="module")
def alb_output(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_backend: BackendOutput,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[_TestAlbOutput]:
    """Apply the ALB module with a self-signed certificate; yield output; destroy on teardown."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent / "self_signed"
    tmp_path = tmp_path_factory.mktemp("test-alb-self-signed")
    tfbackend_path = tmp_path / "test-alb-self-signed.s3.tfbackend"
    tfvars_path = tmp_path / "test-alb-self-signed.tfvars.json"

    with (
        terraform_tfbackend_s3(
            path=tfbackend_path,
            backend=pyfogies_test_backend,
            state=PYFOGIES_TEST_TERRAFORM_BACKEND_STATES.TEST_ALB_SELF_SIGNED.value,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestAlbVars(
                region=pyfogies_test_config.aws.region,
                alb_name=_TEST_ALB_NAME,
            ),
        ) as tfvars_path,
        terraform_output(
            binary_cache_path=PATH_STAGING_BINARY_CACHE,
            command_params=command_params,
            module_path=module_path,
            tfvars_path=tfvars_path,
            tfbackend_path=tfbackend_path,
            init_on_entry=True,
            init_params=InitParams(upgrade=True, reconfigure=True),
            apply_on_entry=True,
            apply_params=ApplyParams(auto_approve=True),
            destroy_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestAlbOutput,
        ) as output,
    ):
        _wait_for_alb(output.alb.alb_dns_name)
        yield output


def _wait_for_alb(dns_name: str, timeout_seconds: int = 120) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            _ = requests.get(
                "http://{}".format(dns_name), timeout=5, allow_redirects=False
            )
            return
        except requests.exceptions.ConnectionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(5)


def test_alb_output(alb_output: _TestAlbOutput) -> None:
    """ALB output contains expected ARNs and DNS name."""
    assert alb_output.alb.alb_arn.startswith("arn:aws:elasticloadbalancing:")
    assert alb_output.alb.alb_dns_name != ""
    assert alb_output.alb.alb_zone_id != ""
    assert alb_output.alb.listener_http_arn.startswith("arn:aws:elasticloadbalancing:")
    assert alb_output.alb.listener_https_arn.startswith("arn:aws:elasticloadbalancing:")
    assert alb_output.alb.certificate_pem is not None


def test_alb_http_redirects_to_https(alb_output: _TestAlbOutput) -> None:
    """HTTP request returns 301 redirect to HTTPS."""
    http_response = requests.get(
        "http://{}".format(alb_output.alb.alb_dns_name),
        allow_redirects=False,
    )
    assert http_response.status_code == 301, "Expected 301 redirect, got: {}".format(
        http_response.status_code
    )
    location = http_response.headers.get("Location", "")
    assert location.startswith(
        "https://"
    ), "Expected redirect to HTTPS, got Location: {}".format(location)


def test_alb_https_reachable(
    alb_output: _TestAlbOutput,
    tmp_path: pathlib.Path,
) -> None:
    """HTTPS is reachable and returns the expected fixed-response body."""
    assert alb_output.alb.certificate_pem is not None
    pem_path = tmp_path / "certificate.pem"
    _ = pem_path.write_text(alb_output.alb.certificate_pem)

    https_response = requests.get(
        "https://{}".format(alb_output.alb.alb_dns_name),
        verify=str(pem_path),
    )
    assert (
        https_response.status_code == 503
    ), "Expected fixed-response 503, got: {}".format(https_response.status_code)
    expected_body = "No listener rule matched this request.\nname: {}\narn: {}".format(
        _TEST_ALB_NAME,
        alb_output.alb.alb_arn,
    )
    assert (
        https_response.text == expected_body
    ), "Expected fixed-response body, got: {}".format(https_response.text)
