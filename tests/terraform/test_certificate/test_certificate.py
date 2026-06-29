"""Test Terraform certificate module."""

import os
import pathlib

import pytest
from fogies_paths import PATH_STAGING_BINARY_CACHE
from pydantic import BaseModel

from fogies.terraform.backend import BackendOutput
from fogies.terraform.certificate import CertificateOutput, CertificateVars
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfbackend_s3,
    terraform_tfvars,
)
from tests.terraform.backend import (
    PYFOGIES_TEST_TERRAFORM_BACKEND_REGION,
    PYFOGIES_TEST_TERRAFORM_BACKEND_STATES,
)

_TEST_REGION = PYFOGIES_TEST_TERRAFORM_BACKEND_REGION
_TEST_ZONE_NAME_ENV = "PYFOGIES_TEST_CERTIFICATE_ZONE_NAME"
_TEST_DOMAINS_ENV = "PYFOGIES_TEST_CERTIFICATE_DOMAINS"

_requires_domain = pytest.mark.skipif(
    _TEST_ZONE_NAME_ENV not in os.environ or _TEST_DOMAINS_ENV not in os.environ,
    reason="{} and {} environment variables not set".format(
        _TEST_ZONE_NAME_ENV, _TEST_DOMAINS_ENV
    ),
)


class _TestCertificateOutput(BaseModel):
    certificate: CertificateOutput


@_requires_domain
def test_certificate_output(
    pyfogies_test_backend: BackendOutput,
    tmp_path: pathlib.Path,
) -> None:
    """Certificate module creates a DNS-validated ACM certificate."""
    zone_name = os.environ[_TEST_ZONE_NAME_ENV]
    domains = os.environ[_TEST_DOMAINS_ENV].split(",")
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent
    tfbackend_path = tmp_path / "test-certificate.s3.tfbackend"
    tfvars_path = tmp_path / "test-certificate.tfvars.json"

    with (
        terraform_tfbackend_s3(
            path=tfbackend_path,
            backend=pyfogies_test_backend,
            state=PYFOGIES_TEST_TERRAFORM_BACKEND_STATES.TEST_CERTIFICATE.value,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=CertificateVars(
                region=_TEST_REGION,
                zone_name=zone_name,
                domains=domains,
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
            output_model=_TestCertificateOutput,
        ) as output,
    ):
        assert isinstance(output.certificate, CertificateOutput)
        assert output.certificate.certificate_arn.startswith("arn:aws:acm:")
