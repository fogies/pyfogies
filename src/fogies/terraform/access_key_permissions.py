"""Pydantic models for Terraform access-key-permissions module output."""

from pydantic import BaseModel, Field, field_validator


class PolicyStatement(BaseModel):
    effect: str = Field(alias="Effect")
    actions: list[str] = Field(alias="Action")
    resources: list[str] = Field(alias="Resource")

    @field_validator("actions", "resources", mode="before")
    @classmethod
    def _normalize_to_list(cls, value: str | list[str]) -> list[str]:
        """IAM renders a single action/resource as a bare string, not a one-item list."""
        return [value] if isinstance(value, str) else value


class PolicyDocument(BaseModel):
    version: str = Field(alias="Version")
    statements: list[PolicyStatement] = Field(alias="Statement")


class AccessKeyPermissionsOutput(BaseModel):
    username: str
    policy_name: str
    policy_json: str

    @property
    def policy(self) -> PolicyDocument:
        """Parse policy_json into a structured PolicyDocument."""
        return PolicyDocument.model_validate_json(self.policy_json)
