"""Pydantic models and helpers for the Terraform backend module."""

import json
import pathlib
import tomllib
from typing import ClassVar, cast

import tomli_w
from pydantic import BaseModel, ConfigDict

from fogies.tools.boto import s3_delete_keys
from fogies.typing import boto_client_s3


class BackendVars(BaseModel):
    name: str
    region: str
    states: list[str]
    tags: dict[str, str] = {}


class BackendConfig(BaseModel):
    """Connection info for a single state within an S3 Terraform backend.

    Unlike a Terraform backend module's output, this does not describe every
    state sharing a backend bucket. It describes only the one state a
    consumer wants to connect to.
    """

    state: str
    bucket_name: str
    region: str
    key: str

    @staticmethod
    def for_state(*, name: str, region: str, state: str) -> "BackendConfig":
        """Return connection config for a state, without applying the backend module.

        Mirrors the bucket and key naming the backend Terraform module derives
        internally, so a tenant can point at an already-applied backend without
        knowing about any other state sharing its bucket.
        """
        return BackendConfig(
            state=state,
            bucket_name="{}-bucket-{}".format(name, region),
            region=region,
            key="{}/terraform.tfstate".format(state),
        )


class BackendOutput(BaseModel):
    bucket_name: str
    region: str
    state_keys: dict[str, str]

    def config(self, *, state: str) -> BackendConfig:
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

        return BackendConfig(
            state=state,
            bucket_name=self.bucket_name,
            region=self.region,
            key=self.state_keys[state],
        )

    def __getitem__(self, state: str) -> BackendConfig:
        return self.config(state=state)


def backend_delete_state_objects(*, output: BackendOutput) -> None:
    """Delete all declared state objects, and their lock files, from the backend bucket.

    Verifies every declared state is empty of resources first; deletes
    nothing, and raises RuntimeError, if any state still has resources.
    Leaves other bucket content untouched.
    """
    states_with_resources = backend_states_with_resources(output=output)
    if states_with_resources:
        lines = [
            "State '{}' still has {} resource(s):\n{}".format(
                state_name,
                len(resources),
                json.dumps(resources, indent=2),
            )
            for state_name, resources in states_with_resources.items()
        ]
        raise RuntimeError(
            "Backend '{}' is not empty; refusing to destroy it.\n{}".format(
                output.bucket_name,
                "\n".join(lines),
            )
        )

    state_keys = set(output.state_keys.values())
    lock_keys = {"{}.tflock".format(key) for key in state_keys}
    s3_delete_keys(
        bucket_name=output.bucket_name,
        region=output.region,
        keys=state_keys | lock_keys,
    )


def backend_state_resources(*, config: BackendConfig) -> list[object]:
    """Return config's resources from the backend bucket.

    Returns an empty list if the state's object is absent (never applied) or
    has no resources.
    """
    client = boto_client_s3(region=config.region)
    try:
        response = client.get_object(Bucket=config.bucket_name, Key=config.key)
    except client.exceptions.NoSuchKey:
        return []

    body = response["Body"].read().decode()
    state_json = cast(dict[str, object], json.loads(body))
    return cast(list[object], state_json.get("resources", []))


def backend_states_with_resources(*, output: BackendOutput) -> dict[str, list[object]]:
    """Return each declared state that still has resources, mapped to its resources.

    Empty if every declared state is empty.
    """
    states_with_resources: dict[str, list[object]] = {}
    for state in output.state_keys:
        resources = backend_state_resources(config=output.config(state=state))
        if resources:
            states_with_resources[state] = resources
    return states_with_resources


class BackendStatusEntry(BaseModel):
    # strict: this file only ever holds genuine TOML booleans, written by us.
    # A stray "yes" or 1 from hand-editing should fail loudly, not coerce.
    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True)

    applied: bool = False


class BackendStatus(BaseModel):
    """Whether a backend, and the states using it, are applied - as last recorded.

    A given file is unique to a single backend: one bucket, not a registry
    of several. This is not a source of truth: it goes stale if applied or
    destroyed some other way than the tasks that maintain it. Intended to
    be committed: changes are rare, since they only happen on a successful
    apply or destroy. Not round-trip preserving: saving always regenerates
    the file from this schema.

    Load once, read or mutate the fields directly, and save when done -
    rather than re-reading the file for every question. For example:

        status = BackendStatus.load(path=path)
        status.backend.applied = True
        applied = status.states.get(name, BackendStatusEntry()).applied
        status.states[name] = BackendStatusEntry(applied=True)
        status.save(path=path)
    """

    backend: BackendStatusEntry = BackendStatusEntry()
    states: dict[str, BackendStatusEntry] = {}

    @staticmethod
    def load(*, path: pathlib.Path) -> "BackendStatus":
        """Load and validate path, or return an all-False status if absent.

        Raises a pydantic ValidationError if path's contents do not match
        the expected schema.
        """
        if not path.exists():
            return BackendStatus()
        with path.open("rb") as f:
            data = tomllib.load(f)
        return BackendStatus.model_validate(data)

    def save(self, *, path: pathlib.Path) -> None:
        """Write self to path as TOML, creating parent directories as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            tomli_w.dump(self.model_dump(mode="json"), f)
