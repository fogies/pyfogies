"""Fixtures for the pyfogies-test-certificate shared self-signed certificate."""

import pathlib
from collections.abc import Iterator

import pytest
from fogies_paths import PATH_STAGING_BINARY_CACHE
from pydantic import BaseModel

from fogies.terraform.backend import BackendOutput
from fogies.terraform.certificate import CertificateOutput
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


class _PyfogiesTestCertificateVars(BaseModel):
    region: str


class _PyfogiesTestCertificateOutput(BaseModel):
    certificate: CertificateOutput


@pytest.fixture(scope="session")
def pyfogies_test_certificate(
    pyfogies_test_backend: BackendOutput,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[CertificateOutput]:
    """Apply a self-signed ACM certificate; yield its ARN; destroy on teardown."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).resolve().parent
    tmp_path = tmp_path_factory.mktemp("pyfogies-test-certificate")
    tfbackend_path = tmp_path / "pyfogies-test-certificate.s3.tfbackend"
    tfvars_path = tmp_path / "pyfogies-test-certificate.tfvars.json"

    with (
        terraform_tfbackend_s3(
            path=tfbackend_path,
            backend=pyfogies_test_backend,
            state=PYFOGIES_TEST_TERRAFORM_BACKEND_STATES.PYFOGIES_TEST_CERTIFICATE.value,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_PyfogiesTestCertificateVars(
                region=PYFOGIES_TEST_TERRAFORM_BACKEND_REGION,
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
            output_model=_PyfogiesTestCertificateOutput,
        ) as output,
    ):
        yield output.certificate
