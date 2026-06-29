"""Pydantic models for Terraform certificate module variables and output."""

from pydantic import BaseModel


class CertificateVars(BaseModel):
    region: str
    zone_name: str
    domains: list[str]
    tags: dict[str, str] = {}


class CertificateOutput(BaseModel):
    certificate_arn: str
