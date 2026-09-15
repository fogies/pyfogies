"""Pydantic models for Terraform ECS module output."""

from pydantic import BaseModel


class EcsOutput(BaseModel):
    cluster_arn: str
    service_name: str
    task_definition_arn: str
    target_group_arn: str
