"""Test Terraform ALB module."""

import pathlib

from fogies_paths import PATH_STAGING_BINARY_CACHE
from pydantic import BaseModel

from fogies.terraform.alb import AlbOutput
from fogies.terraform.backend import BackendOutput
from fogies.terraform.certificate import CertificateOutput
from fogies.terraform.network import NetworkOutput
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfbackend_s3,
    terraform_tfvars,
)
from tests.terraform.backend import PYFOGIES_TEST_TERRAFORM_BACKEND_STATES


_TEST_ALB_NAME = "pyfogies-test-alb"


class _TestAlbVars(BaseModel):
    region: str
    alb_name: str
    certificate_arn: str


class _TestAlbOutput(BaseModel):
    network: NetworkOutput
    alb: AlbOutput


def test_alb_output(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_backend: BackendOutput,
    pyfogies_test_certificate: CertificateOutput,
    tmp_path: pathlib.Path,
) -> None:
    """ALB module creates a load balancer with HTTP redirect and HTTPS listener."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent
    tfbackend_path = tmp_path / "test-alb.s3.tfbackend"
    tfvars_path = tmp_path / "test-alb.tfvars.json"

    with (
        terraform_tfbackend_s3(
            path=tfbackend_path,
            backend=pyfogies_test_backend,
            state=PYFOGIES_TEST_TERRAFORM_BACKEND_STATES.TEST_ALB.value,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestAlbVars(
                region=pyfogies_test_config.aws.region,
                alb_name=_TEST_ALB_NAME,
                certificate_arn=pyfogies_test_certificate.certificate_arn,
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
            delete_on_exit=True,
            destroy_params=DestroyParams(auto_approve=True),
            output_model=_TestAlbOutput,
        ) as output,
    ):
        assert isinstance(output.alb, AlbOutput)
        assert output.alb.alb_arn.startswith("arn:aws:elasticloadbalancing:")
        assert output.alb.alb_dns_name != ""
        assert output.alb.alb_zone_id != ""
        assert output.alb.listener_http_arn.startswith("arn:aws:elasticloadbalancing:")
        assert output.alb.listener_https_arn.startswith("arn:aws:elasticloadbalancing:")
