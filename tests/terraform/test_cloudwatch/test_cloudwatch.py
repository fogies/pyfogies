"""Test Terraform CloudWatch module."""

import pathlib
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_logs.type_defs import OutputLogEventTypeDef

import pytest
from pydantic import BaseModel

from fogies.ready_poll import READY_POLL_TIMING_SHORT, ready_poll
from fogies.terraform.backend import BackendOutput
from fogies.terraform.cloudwatch import CloudwatchOutput
from fogies.tools.command import CommandParams
from fogies.tools.terraform import (
    ApplyParams,
    DestroyParams,
    InitParams,
    terraform_output,
    terraform_tfbackend,
    terraform_tfvars,
)
from fogies.typing import boto_client_logs
from tasks.paths import PATH_STAGING_BINARY_CACHE, PATH_TEST_BACKEND_STATUS
from tests.pyfogies_tests_config import PyfogiesTestsConfig
from tests.terraform.backend import PyfogiesTestTerraformBackendStates

_TEST_LOG_GROUP_NAME = "/pyfogies/test-cloudwatch"
_TEST_LOG_STREAM_NAME = "test-stream"
_TEST_RETENTION_IN_DAYS = 7
_TEST_CLOUDWATCH_TAGS = {"Project": "pyfogies-test-cloudwatch"}


class _TestCloudwatchVars(BaseModel):
    region: str
    log_group_name: str
    retention_in_days: int
    tags: dict[str, str] = {}


class _TestCloudwatchOutput(BaseModel):
    cloudwatch: CloudwatchOutput


@pytest.fixture(scope="module")
def cloudwatch_output(
    pyfogies_test_config: PyfogiesTestsConfig,
    pyfogies_test_backend: BackendOutput,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[_TestCloudwatchOutput]:
    """Apply the CloudWatch module; yield output; destroy on teardown."""
    command_params = CommandParams(in_stream=False)
    module_path = pathlib.Path(__file__).parent
    tmp_path = tmp_path_factory.mktemp("test-cloudwatch")
    tfbackend_path = tmp_path / "test-cloudwatch.tfbackend"
    tfvars_path = tmp_path / "test-cloudwatch.tfvars.json"

    backend = pyfogies_test_backend[
        PyfogiesTestTerraformBackendStates.TEST_CLOUDWATCH.value
    ]

    with (
        terraform_tfbackend(
            path=tfbackend_path,
            backend=backend,
        ) as tfbackend_path,
        terraform_tfvars(
            path=tfvars_path,
            variables=_TestCloudwatchVars(
                region=pyfogies_test_config.aws.region,
                log_group_name=_TEST_LOG_GROUP_NAME,
                retention_in_days=_TEST_RETENTION_IN_DAYS,
                tags=_TEST_CLOUDWATCH_TAGS,
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
            output_model=_TestCloudwatchOutput,
        ) as output,
    ):
        yield output


def test_cloudwatch_output(cloudwatch_output: _TestCloudwatchOutput) -> None:
    """CloudWatch module output contains expected log group name and ARN."""
    assert cloudwatch_output.cloudwatch.log_group_name == _TEST_LOG_GROUP_NAME
    assert cloudwatch_output.cloudwatch.log_group_arn.startswith("arn:aws:logs:")


def test_cloudwatch_write_and_read(
    pyfogies_test_config: PyfogiesTestsConfig,
    cloudwatch_output: _TestCloudwatchOutput,
) -> None:
    """Log group accepts written events and returns them on read."""
    client = boto_client_logs(region=pyfogies_test_config.aws.region)
    message = "pyfogies test-cloudwatch log event"

    _ = client.create_log_stream(
        logGroupName=cloudwatch_output.cloudwatch.log_group_name,
        logStreamName=_TEST_LOG_STREAM_NAME,
    )
    _ = client.put_log_events(
        logGroupName=cloudwatch_output.cloudwatch.log_group_name,
        logStreamName=_TEST_LOG_STREAM_NAME,
        logEvents=[{"timestamp": int(time.time() * 1000), "message": message}],
    )

    events: list[OutputLogEventTypeDef] = []
    for attempt in ready_poll(exceptions=_NoEventsYet, timing=READY_POLL_TIMING_SHORT):
        with attempt:
            response = client.get_log_events(
                logGroupName=cloudwatch_output.cloudwatch.log_group_name,
                logStreamName=_TEST_LOG_STREAM_NAME,
                startFromHead=True,
            )
            events = list(response.get("events", []))
            if not events:
                raise _NoEventsYet("Log event not yet visible")

    assert len(events) == 1, "Expected 1 log event, got {}".format(len(events))
    assert events[0].get("message") == message


class _NoEventsYet(Exception):
    pass
