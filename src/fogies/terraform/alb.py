"""Pydantic models for Terraform ALB module output."""

from pydantic import BaseModel


class AlbOutput(BaseModel):
    alb_arn: str
    alb_dns_name: str
    alb_zone_id: str
    listener_http_arn: str
    listener_https_arn: str
    certificate_pem: str | None
