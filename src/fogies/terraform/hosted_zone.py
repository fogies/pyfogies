"""Pydantic models for Terraform hosted_zone module variables and output."""

from pydantic import BaseModel


class HostedZoneVars(BaseModel):
    zone_name: str
    create_zone: bool


class HostedZoneOutput(BaseModel):
    zone_id: str
    zone_name: str
    name_servers: list[str]
