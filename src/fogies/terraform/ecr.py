"""Pydantic models for Terraform ECR module variables and output."""

from pydantic import BaseModel


class EcrVars(BaseModel):
    region: str
    repositories: list[str]
    lifecycle_keep_count: int
    lifecycle_keep_days: int
    force_delete: bool
    tags: dict[str, str] = {}


class EcrRepositoryOutput(BaseModel):
    name: str
    arn: str
    repository_url: str


class EcrOutput(BaseModel):
    registry_url: str
    repositories: dict[str, EcrRepositoryOutput]
