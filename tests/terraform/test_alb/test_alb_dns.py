"""Test Terraform ALB module with a DNS-validated certificate."""

import pathlib
from collections.abc import Iterator

import pytest
import requests
from pydantic import BaseModel

from fogies.retry import readiness_poll_long
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
from tasks.paths import PATH_STAGING_BINARY_CACHE
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PyfogiesTestTerraformBackendStates

_TEST_ALB_NAME = "pyfogies-test-alb"


class _TestAlbDnsVars(BaseModel):
    region: str
    alb_name: str
    zone_name: str


class _TestAlbDnsOutput(BaseModel):
    network: NetworkOutput
    alb: AlbOutput
    alb_hostname: str


@pytest.fixture(scope="module")
def alb_dns_output(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_backend: BackendOutput,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[_TestAlbDnsOutput]:
    """Apply the ALB module with a DNS-validated certificate; yield output; destroy on teardown.

    Requires a Route 53 hosted zone for the configured domain to already exist.
    Create it once with the terraform/hosted_zone module before running DNS tests.
    """
    if pyfogies_test_config.domain is None:
        pytest.skip(
            "No domain configured; set [domain] zone_name in pyfogies-tests.toml to run DNS tests."
        )

    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent / "dns"
    tmp_path = tmp_path_factory.mktemp("test-alb-dns")
    tfbackend_path = tmp_path / "test-alb-dns.tfbackend"
    tfvars_path = tmp_path / "test-alb-dns.tfvars.json"

    assert pyfogies_test_config.domain is not None
    with (
        terraform_tfbackend(
            path=tfbackend_path,
            backend=pyfogies_test_backend[
                PyfogiesTestTerraformBackendStates.TEST_ALB_DNS.value
            ],
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestAlbDnsVars(
                region=pyfogies_test_config.aws.region,
                alb_name=_TEST_ALB_NAME,
                zone_name=pyfogies_test_config.domain.zone_name,
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
            output_model=_TestAlbDnsOutput,
        ) as output,
    ):
        _wait_for_alb(output.alb_hostname)
        yield output


def _wait_for_alb(hostname: str) -> None:
    for attempt in readiness_poll_long(exceptions=requests.exceptions.ConnectionError):
        with attempt:
            _ = requests.get(
                "http://{}".format(hostname), timeout=5, allow_redirects=False
            )


def test_alb_output(alb_dns_output: _TestAlbDnsOutput) -> None:
    """ALB output contains expected ARNs and DNS name."""
    assert alb_dns_output.alb.alb_arn.startswith("arn:aws:elasticloadbalancing:")
    assert alb_dns_output.alb.alb_dns_name != ""
    assert alb_dns_output.alb.alb_zone_id != ""
    assert alb_dns_output.alb.listener_http_arn.startswith(
        "arn:aws:elasticloadbalancing:"
    )
    assert alb_dns_output.alb.listener_https_arn.startswith(
        "arn:aws:elasticloadbalancing:"
    )
    assert alb_dns_output.alb.certificate_pem is None


def test_alb_http_redirects_to_https(alb_dns_output: _TestAlbDnsOutput) -> None:
    """HTTP request returns 301 redirect to HTTPS."""
    http_response = requests.get(
        "http://{}".format(alb_dns_output.alb_hostname),
        allow_redirects=False,
    )
    assert http_response.status_code == 301, "Expected 301 redirect, got: {}".format(
        http_response.status_code
    )
    location = http_response.headers.get("Location", "")
    assert location.startswith(
        "https://"
    ), "Expected redirect to HTTPS, got Location: {}".format(location)


def test_alb_https_reachable(alb_dns_output: _TestAlbDnsOutput) -> None:
    """HTTPS is reachable with a trusted certificate and returns the expected fixed-response body."""
    https_response = requests.get("https://{}".format(alb_dns_output.alb_hostname))
    assert (
        https_response.status_code == 503
    ), "Expected fixed-response 503, got: {}".format(https_response.status_code)
    expected_body = "No listener rule matched this request.\nname: {}\narn: {}".format(
        _TEST_ALB_NAME,
        alb_dns_output.alb.alb_arn,
    )
    assert (
        https_response.text == expected_body
    ), "Expected fixed-response body, got: {}".format(https_response.text)
