"""Test Terraform ALB module with a self-signed certificate."""

import pathlib

import requests

from fogies.boto_clients import boto_client_elbv2
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.pyfogies_test_alb_self_signed import (
    PyfogiesTestAlbSelfSignedOutput,
)


def test_alb_output(
    pyfogies_test_alb_self_signed: PyfogiesTestAlbSelfSignedOutput,
) -> None:
    """ALB output contains expected ARNs and DNS name."""
    assert pyfogies_test_alb_self_signed.alb.alb_arn.startswith(
        "arn:aws:elasticloadbalancing:"
    )
    assert pyfogies_test_alb_self_signed.alb.alb_dns_name != ""
    assert pyfogies_test_alb_self_signed.alb.alb_zone_id != ""
    assert pyfogies_test_alb_self_signed.alb.listener_http_arn.startswith(
        "arn:aws:elasticloadbalancing:"
    )
    assert pyfogies_test_alb_self_signed.alb.listener_https_arn.startswith(
        "arn:aws:elasticloadbalancing:"
    )
    assert pyfogies_test_alb_self_signed.alb.certificate_pem is not None


def test_alb_https_listener_ssl_policy(
    pyfogies_test_alb_self_signed: PyfogiesTestAlbSelfSignedOutput,
    pyfogies_test_config: PyfogiesTestsConfig,
) -> None:
    """HTTPS listener uses the restricted TLS 1.2 and 1.3 post-quantum security policy."""
    client = boto_client_elbv2(region=pyfogies_test_config.aws.region)
    listeners = client.describe_listeners(
        ListenerArns=[pyfogies_test_alb_self_signed.alb.listener_https_arn]
    )["Listeners"]

    assert len(listeners) == 1
    assert listeners[0].get("SslPolicy") == "ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09"


def test_alb_http_redirects_to_https(
    pyfogies_test_alb_self_signed: PyfogiesTestAlbSelfSignedOutput,
) -> None:
    """HTTP request returns 301 redirect to HTTPS."""
    http_response = requests.get(
        "http://{}".format(pyfogies_test_alb_self_signed.alb.alb_dns_name),
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
    pyfogies_test_alb_self_signed: PyfogiesTestAlbSelfSignedOutput,
    tmp_path: pathlib.Path,
) -> None:
    """HTTPS is reachable and returns the fixed-response body containing the ALB ARN."""
    assert pyfogies_test_alb_self_signed.alb.certificate_pem is not None
    pem_path = tmp_path / "certificate.pem"
    _ = pem_path.write_text(pyfogies_test_alb_self_signed.alb.certificate_pem)

    https_response = requests.get(
        "https://{}".format(pyfogies_test_alb_self_signed.alb.alb_dns_name),
        verify=str(pem_path),
    )
    assert (
        https_response.status_code == 503
    ), "Expected fixed-response 503, got: {}".format(https_response.status_code)
    assert (
        pyfogies_test_alb_self_signed.alb.alb_arn in https_response.text
    ), "Expected ALB ARN in fixed-response body, got: {}".format(https_response.text)
