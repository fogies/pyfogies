"""Test Terraform ECS module."""

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
from fogies.terraform.backend import BackendOutput
from fogies.terraform.cloudwatch import CloudwatchOutput
from fogies.terraform.ecs import EcsOutput
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
from fogies.typing import boto_client_ec2, boto_client_ecs
from tasks.paths import PATH_STAGING_BINARY_CACHE, PATH_TEST_BACKEND_STATUS
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PyfogiesTestTerraformBackendStates
from tests.terraform.pyfogies_test_alb_self_signed import PyfogiesTestAlbOutput

_TEST_ECS_NAME = "pyfogies-test-ecs"


class _TestEcsVars(BaseModel):
    region: str
    name: str
    vpc_id: str
    subnet_ids: list[str]
    alb_security_group_id: str
    listener_https_arn: str


class _TestEcsOutput(BaseModel):
    cloudwatch: CloudwatchOutput
    ecs: EcsOutput


@pytest.fixture(scope="module")
def ecs_output(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_backend: BackendOutput,
    pyfogies_test_network: NetworkOutput,
    pyfogies_test_alb_self_signed: PyfogiesTestAlbOutput,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[_TestEcsOutput]:
    """Apply CloudWatch and ECS modules using the shared ALB; yield output; destroy on teardown."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent
    tmp_path = tmp_path_factory.mktemp("test-ecs")
    tfbackend_path = tmp_path / "test-ecs.tfbackend"
    tfvars_path = tmp_path / "test-ecs.tfvars.json"
    pem_tmp = tmp_path / "certificate.pem"

    backend = pyfogies_test_backend[PyfogiesTestTerraformBackendStates.TEST_ECS.value]

    with (
        terraform_tfbackend(
            path=tfbackend_path,
            backend=backend,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestEcsVars(
                region=pyfogies_test_config.aws.region,
                name=_TEST_ECS_NAME,
                vpc_id=pyfogies_test_network.vpc_id,
                subnet_ids=pyfogies_test_network.subnet_ids,
                alb_security_group_id=pyfogies_test_alb_self_signed.alb_security_group_id,
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
            output_model=_TestEcsOutput,
        ) as output,
    ):
        _wait_for_ecs(pyfogies_test_alb_self_signed, pem_tmp)
        yield output


def _wait_for_ecs(alb: PyfogiesTestAlbOutput, pem_tmp: pathlib.Path) -> None:
    """Poll the ALB until the ECS service is healthy and serving traffic."""
    verify: str | bool
    if alb.alb.certificate_pem is not None:
        _ = pem_tmp.write_text(alb.alb.certificate_pem)
        verify = str(pem_tmp)
    else:
        verify = True

    for attempt in ready_poll(
        exceptions=READY_POLL_EXCEPTIONS_HTTP,
        timing=READY_POLL_TIMING_LONG,
    ):
        with attempt:
            response = requests.get(
                "https://{}".format(alb.alb.alb_dns_name),
                verify=verify,
                timeout=5,
                allow_redirects=False,
            )
            response.raise_for_status()


def _get_task_public_ip(*, cluster_arn: str, service_name: str, region: str) -> str:
    """Return the public IP of a running ECS Fargate task in the given service."""
    ecs = boto_client_ecs(region=region)
    ec2 = boto_client_ec2(region=region)

    task_arns = ecs.list_tasks(cluster=cluster_arn, serviceName=service_name)[
        "taskArns"
    ]
    tasks = ecs.describe_tasks(cluster=cluster_arn, tasks=task_arns)["tasks"]

    for task in tasks:
        for attachment in task.get("attachments", []):
            if attachment.get("type") == "ElasticNetworkInterface":
                for detail in attachment.get("details", []):
                    if detail.get("name") == "networkInterfaceId":
                        eni_id: str = detail.get("value", "")
                        interfaces = ec2.describe_network_interfaces(
                            NetworkInterfaceIds=[eni_id]
                        )["NetworkInterfaces"]
                        if interfaces:
                            association = interfaces[0].get("Association", {})
                            public_ip: str = association.get("PublicIp", "")
                            if public_ip:
                                return public_ip

    raise RuntimeError(
        "No running task with a public IP found in service {}".format(service_name)
    )


def test_ecs_output(ecs_output: _TestEcsOutput) -> None:
    """ECS module output contains expected ARNs and names."""
    assert ecs_output.ecs.cluster_arn.startswith("arn:aws:ecs:")
    assert ecs_output.ecs.service_name == _TEST_ECS_NAME
    assert ecs_output.ecs.task_definition_arn.startswith("arn:aws:ecs:")
    assert ecs_output.ecs.target_group_arn.startswith("arn:aws:elasticloadbalancing:")


def test_ecs_https_serves_nginx(
    ecs_output: _TestEcsOutput,
    pyfogies_test_alb_self_signed: PyfogiesTestAlbOutput,
    tmp_path: pathlib.Path,
) -> None:
    """HTTPS request reaches the ECS service and nginx returns 200."""
    _ = ecs_output
    verify: str | bool
    if pyfogies_test_alb_self_signed.alb.certificate_pem is not None:
        pem_path = tmp_path / "certificate.pem"
        _ = pem_path.write_text(pyfogies_test_alb_self_signed.alb.certificate_pem)
        verify = str(pem_path)
    else:
        verify = True

    response = requests.get(
        "https://{}".format(pyfogies_test_alb_self_signed.alb.alb_dns_name),
        verify=verify,
    )
    assert response.status_code == 200, "Expected 200 from nginx, got: {}".format(
        response.status_code
    )
    assert "nginx" in response.text.lower(), "Expected nginx response body"


def test_ecs_direct_access_blocked(
    ecs_output: _TestEcsOutput,
    pyfogies_test_config: PyfogiesTestsConfig,
) -> None:
    """Direct HTTP to the ECS task public IP is blocked by the security group."""
    task_ip = _get_task_public_ip(
        cluster_arn=ecs_output.ecs.cluster_arn,
        service_name=ecs_output.ecs.service_name,
        region=pyfogies_test_config.aws.region,
    )
    with pytest.raises(requests.exceptions.ConnectionError):
        _ = requests.get("http://{}".format(task_ip), timeout=5)
