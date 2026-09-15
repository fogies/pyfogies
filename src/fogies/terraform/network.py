"""Pydantic models for Terraform network module output."""

from pydantic import BaseModel


class NetworkOutput(BaseModel):
    vpc_id: str
    subnet_ids: list[str]
    availability_zone_to_subnet_id: dict[str, str]
