"""Pydantic models for Terraform hosted_zone module output."""

from pydantic import BaseModel


class HostedZoneOutput(BaseModel):
    zone_id: str
    zone_name: str
    name_servers: list[str]
