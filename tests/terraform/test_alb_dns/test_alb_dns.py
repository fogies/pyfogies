"""Test ALB reachability via a Route 53 DNS alias record."""

import pathlib
import socket
from collections.abc import Iterator

import pytest
import requests
from pydantic import BaseModel

from fogies.ready_poll import (
    READY_POLL_EXCEPTIONS_DNS,
    READY_POLL_EXCEPTIONS_HTTP,
    READY_POLL_TIMING_LONG,
    ready_poll,
)
from fogies.terraform.backend import BackendOutput
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
from tests.terraform.pyfogies_test_alb_self_signed import PyfogiesTestAlbOutput


class _AlbDnsVars(BaseModel):
    region: str
    hosted_zone_name: str
    alb_dns_name: str
    alb_zone_id: str
    listener_https_arn: str


class _AlbDnsOutput(BaseModel):
    hostname: str
    hostnames: list[str]


@pytest.fixture(scope="module")
def alb_dns_output(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_backend: BackendOutput,
    pyfogies_test_alb_self_signed: PyfogiesTestAlbOutput,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[_AlbDnsOutput]:
    """Create a Route 53 alias record pointing to the shared ALB; yield output; destroy on teardown.

    Skipped when [domain] is absent from pyfogies-tests.toml.
    """
    if pyfogies_test_config.domain is None:
        pytest.skip("domain not configured in pyfogies-tests.toml")

    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent
    tmp_path = tmp_path_factory.mktemp("test-alb-dns")
    tfbackend_path = tmp_path / "test-alb-dns.tfbackend"
    tfvars_path = tmp_path / "test-alb-dns.tfvars.json"
    backend = pyfogies_test_backend[
        PyfogiesTestTerraformBackendStates.TEST_ALB_DNS.value
    ]

    with (
        terraform_tfbackend(
            path=tfbackend_path,
            backend=backend,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_AlbDnsVars(
                region=pyfogies_test_config.aws.region,
                hosted_zone_name=pyfogies_test_config.domain.zone_name,
                alb_dns_name=pyfogies_test_alb_self_signed.alb.alb_dns_name,
                alb_zone_id=pyfogies_test_alb_self_signed.alb.alb_zone_id,
                listener_https_arn=pyfogies_test_alb_self_signed.alb.listener_https_arn,
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
            output_model=_AlbDnsOutput,
        ) as output,
    ):
        for hostname in output.hostnames:
            _wait_for_dns(hostname)
            _wait_for_https(hostname)
        yield output


def _wait_for_dns(hostname: str) -> None:
    for attempt in ready_poll(
        exceptions=READY_POLL_EXCEPTIONS_DNS, timing=READY_POLL_TIMING_LONG
    ):
        with attempt:
            _ = socket.getaddrinfo(hostname, None)


def _wait_for_https(hostname: str) -> None:
    for attempt in ready_poll(
        exceptions=READY_POLL_EXCEPTIONS_HTTP, timing=READY_POLL_TIMING_LONG
    ):
        with attempt:
            _ = requests.get(
                "https://{}".format(hostname), timeout=5, allow_redirects=False
            )


def test_alb_dns_http_redirects_to_https(alb_dns_output: _AlbDnsOutput) -> None:
    """HTTP request to each hostname returns a 301 redirect to HTTPS."""
    for hostname in alb_dns_output.hostnames:
        response = requests.get(
            "http://{}".format(hostname),
            timeout=5,
            allow_redirects=False,
        )
        assert response.status_code == 301, "{}: expected 301, got {}".format(
            hostname, response.status_code
        )
        assert response.headers.get("Location", "").startswith(
            "https://"
        ), "{}: expected HTTPS redirect, got Location: {}".format(
            hostname, response.headers.get("Location", "")
        )


def test_alb_dns_https_reachable(alb_dns_output: _AlbDnsOutput) -> None:
    """HTTPS request to each hostname succeeds with the ACM certificate."""
    for hostname in alb_dns_output.hostnames:
        response = requests.get("https://{}".format(hostname), timeout=5)
        assert (
            response.status_code == 503
        ), "{}: expected ALB fixed-response 503, got {}".format(
            hostname, response.status_code
        )
