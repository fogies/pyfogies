"""Test Terraform ALB module with a self-signed certificate."""

import pathlib

import requests

from tests.terraform.pyfogies_test_alb_self_signed import PyfogiesTestAlbOutput


def test_alb_output(pyfogies_test_alb_self_signed: PyfogiesTestAlbOutput) -> None:
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


def test_alb_http_redirects_to_https(
    pyfogies_test_alb_self_signed: PyfogiesTestAlbOutput,
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
    pyfogies_test_alb_self_signed: PyfogiesTestAlbOutput,
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
