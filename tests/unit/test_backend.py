"""Unit tests for fogies.terraform.backend."""

import pathlib

from fogies.terraform.backend import BackendStatus, BackendStatusEntry


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
