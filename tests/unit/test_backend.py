"""Unit tests for fogies.terraform.backend."""

import pathlib

import pytest

from fogies.terraform.backend import (
    BackendConfig,
    BackendStatus,
    BackendStatusEntry,
)


def test_backend_status_load_missing_file(tmp_path: pathlib.Path) -> None:
    status = BackendStatus.load(path=tmp_path / "status.toml")
    assert status == BackendStatus()


def test_backend_status_round_trip(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "status.toml"
    status = BackendStatus()

    status.backend.applied = True
    status.states["state-a"] = BackendStatusEntry(applied=True)
    status.save(path=path)
    assert BackendStatus.load(path=path) == status

    status.backend.applied = False
    status.states["state-a"] = BackendStatusEntry(applied=False)
    status.states["state-b"] = BackendStatusEntry(applied=True)
    status.save(path=path)
    assert BackendStatus.load(path=path) == status


def test_backend_config_bucket_name_length_limit() -> None:
    """The longest name that fits in S3's limit is accepted, one more is not."""
    longest = BackendConfig.for_state(
        backend_name="x" * 37, region="us-west-2", state_name="state-a"
    ).bucket_name(account_id="111122223333")
    assert len(longest) == 63

    with pytest.raises(ValueError):
        _ = BackendConfig.for_state(
            backend_name="x" * 38, region="us-west-2", state_name="state-a"
        ).bucket_name(account_id="111122223333")


def test_backend_config_bucket_name() -> None:
    """The bucket name has the account regional namespace suffix."""
    config = BackendConfig.for_state(
        backend_name="my-backend", region="us-west-2", state_name="state-a"
    )

    assert (
        config.bucket_name(account_id="111122223333")
        == "my-backend-111122223333-us-west-2-an"
    )
