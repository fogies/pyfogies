"""Pydantic models for Terraform backend module variables and output."""

from pydantic import BaseModel


class BackendVars(BaseModel):
    name: str
    region: str
    states: list[str]
    tags: dict[str, str] = {}
    force_destroy: bool


class BackendConfigS3(BaseModel):
    """Connection info for a single state within an S3 Terraform backend.

    Unlike a Terraform backend module's output, this does not describe every
    state sharing a backend bucket. It describes only the one state a
    consumer wants to connect to.
    """

    bucket_name: str
    region: str
    key: str

    @staticmethod
    def for_state(*, name: str, region: str, state: str) -> "BackendConfigS3":
        """Return connection config for a state, without applying the backend module.

        Mirrors the bucket and key naming the backend Terraform module derives
        internally, so a tenant can point at an already-applied backend without
        knowing about any other state sharing its bucket.
        """
        return BackendConfigS3(
            bucket_name="{}-bucket-{}".format(name, region),
            region=region,
            key="{}/terraform.tfstate".format(state),
        )


class BackendOutput(BaseModel):
    bucket_name: str
    region: str
    state_keys: dict[str, str]

    def config(self, *, state: str) -> BackendConfigS3:
        """Return connection config for one of this backend's declared states.

        Raises ValueError if state is not declared as part of the backend.
        """
        if state not in self.state_keys:
            raise ValueError(
                "State '{}' is not declared as part of backend. Declared states: {}.".format(
                    state,
                    ", ".join(sorted(self.state_keys)),
                )
            )

        return BackendConfigS3(
            bucket_name=self.bucket_name,
            region=self.region,
            key=self.state_keys[state],
        )

    def __getitem__(self, state: str) -> BackendConfigS3:
        return self.config(state=state)
