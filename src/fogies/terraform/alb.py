"""Pydantic models for Terraform ALB module variables and output."""

from pydantic import BaseModel


class AlbVars(BaseModel):
    region: str
    name: str
    subnet_ids: list[str]
    security_group_ids: list[str]
    self_signed_certificate: bool = False
    certificate_arn: str | None = None
    tags: dict[str, str] = {}


class AlbOutput(BaseModel):
    alb_arn: str
    alb_dns_name: str
    alb_zone_id: str
    listener_http_arn: str
    listener_https_arn: str
    certificate_pem: str | None
