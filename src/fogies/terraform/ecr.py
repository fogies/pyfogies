"""Pydantic models for Terraform ECR module output."""

from pydantic import BaseModel


class EcrRepositoryOutput(BaseModel):
    name: str
    arn: str
    repository_url: str


class EcrOutput(BaseModel):
    registry_url: str
    repositories: dict[str, EcrRepositoryOutput]
