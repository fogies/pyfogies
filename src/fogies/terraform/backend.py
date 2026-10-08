"""Pydantic models and helpers for the Terraform backend module."""

import json
import pathlib
from typing import ClassVar, cast

import tomlkit
from pydantic import BaseModel, ConfigDict
from tomlkit.items import Table

from fogies.boto_clients import boto_client_s3
from fogies.templates import backend_status_toml_template_factory, ensure_from_template
from fogies.tools.boto import s3_delete_keys


class BackendVars(BaseModel):
    backend_name: str
    region: str
    state_names: list[str]
    tags: dict[str, str] = {}


# S3 limits the length of a bucket name.
_BUCKET_NAME_MAX_LENGTH = 63


class BackendConfig(BaseModel):
    """Connection config for a single state within an S3 Terraform backend.

    The bucket name includes the AWS account ID, which is not stored in code.
    A config is safe to create at import time; bucket_name() is given the
    account ID (e.g. from AwsEnviron) when the bucket is actually needed. This
    lets a tenant point at an already-applied backend without knowing about
    any other state sharing its bucket.
    """

    state_name: str
    backend_name: str
    region: str
    key: str

    @staticmethod
    def for_state(
        *, backend_name: str, region: str, state_name: str
    ) -> "BackendConfig":
        """Return config for a state, without applying the backend module.

        Mirrors the key naming the backend Terraform module derives
        internally, so a tenant can point at an already-applied backend without
        knowing about any other state sharing its bucket.
        """
        return BackendConfig(
            state_name=state_name,
            backend_name=backend_name,
            region=region,
            key="{}/terraform.tfstate".format(state_name),
        )

    def bucket_name(self, *, account_id: str) -> str:
        """Return the name of the backend bucket in the given account.

        Mirrors the bucket naming of the backend Terraform module. Raises
        ValueError if the backend name leaves no room for the account and
        region suffix.
        """
        bucket_name = "{}-{}-{}-an".format(self.backend_name, account_id, self.region)
        if len(bucket_name) > _BUCKET_NAME_MAX_LENGTH:
            raise ValueError(
                "Backend name '{}' makes a bucket name longer than {} characters".format(
                    self.backend_name,
                    _BUCKET_NAME_MAX_LENGTH,
                )
            )
        return bucket_name


class BackendOutput(BaseModel):
    backend_name: str
    bucket_name: str
    region: str
    state_keys: dict[str, str]

    def config(self, *, state_name: str) -> BackendConfig:
        """Return connection config for one of this backend's declared states.

        Raises ValueError if state_name is not declared as part of the backend.
        """
        if state_name not in self.state_keys:
            raise ValueError(
                "State '{}' is not declared as part of backend. Declared states: {}.".format(
                    state_name,
                    ", ".join(sorted(self.state_keys)),
                )
            )

        return BackendConfig(
            state_name=state_name,
            backend_name=self.backend_name,
            region=self.region,
            key=self.state_keys[state_name],
        )

    def __getitem__(self, state_name: str) -> BackendConfig:
        return self.config(state_name=state_name)


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


def backend_state_resources(*, config: BackendConfig, account_id: str) -> list[object]:
    """Return config's resources from the backend bucket.

    Returns an empty list if the state's object is absent (never applied) or
    has no resources.
    """
    return _state_resources(
        bucket_name=config.bucket_name(account_id=account_id),
        region=config.region,
        key=config.key,
    )


def _state_resources(*, bucket_name: str, region: str, key: str) -> list[object]:
    client = boto_client_s3(region=region)
    try:
        response = client.get_object(Bucket=bucket_name, Key=key)
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
    for state_name in output.state_keys:
        resources = _state_resources(
            bucket_name=output.bucket_name,
            region=output.region,
            key=output.state_keys[state_name],
        )
        if resources:
            states_with_resources[state_name] = resources
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
    apply or destroy. Round-trip preserving: saving updates only the keys
    this schema knows about, leaving any other comments or content in the
    file untouched. A brand new file is seeded from a template with an
    explanatory header, since it's committed and meant to be read by people
    browsing the repo, not just tooling.

    Load once, read or mutate the fields directly, and save when done -
    rather than re-reading the file for every question. For example:

        status = BackendStatus.load(path=path)
        status.backend.applied = True
        applied = status.states.get(state_name, BackendStatusEntry()).applied
        status.states[state_name] = BackendStatusEntry(applied=True)
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
        with path.open("r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())
        return BackendStatus.model_validate(doc.unwrap())

    def save(self, *, path: pathlib.Path) -> None:
        """Write self to path as TOML, preserving comments and formatting.

        Updates the existing file's document in place if path already
        exists, so any comments (including a hand-added one) survive.
        Otherwise seeds a new file from backend_status_toml_template_factory().
        """
        ensure_from_template(
            path=path,
            template_factory=backend_status_toml_template_factory,
            raise_if_file_not_found=False,
        )
        with path.open("r", encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())

        if "backend" not in doc:
            doc["backend"] = tomlkit.table()
        backend_table = cast(Table, doc["backend"])
        backend_table["applied"] = self.backend.applied

        if self.states:
            if "states" not in doc:
                doc["states"] = tomlkit.table(is_super_table=True)
            states_table = cast(Table, doc["states"])
            for state_name, entry in self.states.items():
                if state_name not in states_table:
                    states_table[state_name] = tomlkit.table()
                state_table = cast(Table, states_table[state_name])
                state_table["applied"] = entry.applied

        with path.open("w", encoding="utf-8", newline="\n") as f:
            _ = f.write(tomlkit.dumps(doc))
