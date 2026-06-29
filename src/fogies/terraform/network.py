"""Pydantic models for Terraform network module variables and output."""

from pydantic import BaseModel


class NetworkVars(BaseModel):
    region: str
    availability_zone_count: int
    tags: dict[str, str] = {}


class NetworkOutput(BaseModel):
    vpc_id: str
    subnet_ids: list[str]
    availability_zone_to_subnet_id: dict[str, str]
    security_group_ids: list[str]
