"""Pydantic models for Terraform backend module variables and output."""

from pydantic import BaseModel


class BackendVars(BaseModel):
    name: str
    states: list[str] = []
    tags: dict[str, str] = {}
    force_destroy: bool = False


class BackendOutput(BaseModel):
    bucket_name: str
    lock_name: str
    state_keys: dict[str, str]
