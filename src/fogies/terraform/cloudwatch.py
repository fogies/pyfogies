"""Pydantic models for Terraform CloudWatch module output."""

from pydantic import BaseModel


class CloudwatchOutput(BaseModel):
    log_group_name: str
    log_group_arn: str
