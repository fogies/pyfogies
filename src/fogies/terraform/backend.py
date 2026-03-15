"""Pydantic models for Terraform backend module variables and output."""

from pydantic import BaseModel


class BackendVars(BaseModel):
    name: str
    region: str
    states: list[str] = []
    tags: dict[str, str] = {}
    force_destroy: bool = False


class BackendOutput(BaseModel):
    bucket_name: str
    region: str
    state_keys: dict[str, str]
