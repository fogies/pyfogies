import io
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPResponse
from typing import cast

import ollama as _ollama_client
import psutil
from filelock import BaseFileLock, FileLock
from pydantic import BaseModel

_KNOWN_VERSIONS = [
    "0.17.7",
]

_DEFAULT_VERSION = _KNOWN_VERSIONS[-1]

_OLLAMA_URL_TEMPLATE = (
    "https://github.com/ollama/ollama/releases/download"
    "/v{version}/ollama-windows-amd64.zip"
)

_OLLAMA_LISTEN_ADDRESS: tuple[str, int] = ("127.0.0.1", 11434)
_OLLAMA_LISTEN_PROBE_TIMEOUT = 0.25
_OLLAMA_LISTEN_POLL_INTERVAL = 0.1
_OLLAMA_LISTEN_PROBE_WAIT_TIMEOUT = 10.0
_OLLAMA_TERMINATE_WAIT_TIMEOUT = 10.0


class _PidWithCreateTime(BaseModel):
    """Persisted process identity state."""

    pid: int
    create_time: float | None


class _Ollama:
    """Represents an Ollama CLI binary."""

    _version: str
    _path: pathlib.Path
    _file_lock: BaseFileLock

    def __init__(self, *, version: str, path: pathlib.Path) -> None:
        self._version = version
        self._path = path
        self._file_lock = FileLock(str(self._lock_path), is_singleton=True)

    @property
    def binary_version(self) -> str:
        """The Ollama binary version string."""
        return self._version

    @property
    def binary_path(self) -> pathlib.Path:
        """The path to the Ollama executable."""
        return self._path

    @property
    def _pid_path(self) -> pathlib.Path:
        """Return the PID file path for this binary."""
        return self._path.with_suffix(".pid")

    @property
    def _refcount_path(self) -> pathlib.Path:
        """Return the refcount file path for this binary."""
        return self._path.with_suffix(".refcount")

    @property
    def _lock_path(self) -> pathlib.Path:
        """Return the lock file path for this binary."""
        return self._path.with_suffix(".lock")

    @property
    def pid(self) -> _PidWithCreateTime | None:
        """Return process identity state, or None if not managed."""
        self._assert_lock()

        pid_path = self._pid_path
        if not pid_path.exists():
            return None

        text = pid_path.read_text(encoding="utf-8").strip()
        assert text is not None

        state = _PidWithCreateTime.model_validate_json(text)
        assert state.pid > 0

        return state

    @property
    def refcount(self) -> int:
        """Return the server refcount, or 0 if not managed."""
        self._assert_lock()

        refcount_path = self._refcount_path
        if not refcount_path.exists():
            return 0

        text = refcount_path.read_text(encoding="utf-8").strip()
        if not text:
            return 0

        return int(text)

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Acquire and hold the file lock."""
        with self._file_lock:
            yield

    def _assert_lock(self) -> None:
        assert (
            self._file_lock.is_locked
        ), "Must be accessed within an Ollama lock context."

    def reset_state(self) -> None:
        """Clear the server state files."""
        self._assert_lock()

        self._pid_path.unlink(missing_ok=True)
        self._refcount_path.unlink(missing_ok=True)

    def set_pid(self, pid: _PidWithCreateTime) -> None:
        """Set the managed server PID state."""
        self._assert_lock()

        pid_path = self._pid_path

        text = "{}\n".format(pid.model_dump_json())
        _ = pid_path.write_text(text, encoding="utf-8")

    def set_refcount(self, count: int) -> None:
        """Set the managed server refcount state."""
        self._assert_lock()

        refcount_path = self._refcount_path

        _ = refcount_path.write_text(
            "{}\n".format(count),
            encoding="utf-8",
        )


def _terminate_pid(*, pid: _PidWithCreateTime) -> None:
    try:
        process = psutil.Process(pid.pid)

        # If the process has been restarted, the pid was reused, do not terminate it.
        if pid.create_time is not None and process.create_time() != pid.create_time:
            return

        children = process.children(recursive=True)
        processes = [*children, process]

        for process_to_end in processes:
            try:
                process_to_end.terminate()
            except psutil.Error:
                pass

        _, alive = psutil.wait_procs(
            processes,
            timeout=_OLLAMA_TERMINATE_WAIT_TIMEOUT,
        )
        if not alive:
            return

        for process_to_kill in alive:
            try:
                process_to_kill.kill()
            except psutil.Error:
                pass

        _ = psutil.wait_procs(
            alive,
            timeout=_OLLAMA_TERMINATE_WAIT_TIMEOUT,
        )
    except psutil.Error:
        pass


def _wait_until_listening(
    *,
    timeout_s: float = _OLLAMA_LISTEN_PROBE_WAIT_TIMEOUT,
) -> None:
    end = time.time() + timeout_s
    while time.time() < end:
        try:
            with socket.create_connection(
                _OLLAMA_LISTEN_ADDRESS,
                timeout=_OLLAMA_LISTEN_PROBE_TIMEOUT,
            ):
                return
        except OSError:
            pass
        time.sleep(_OLLAMA_LISTEN_POLL_INTERVAL)
    raise TimeoutError("Ollama server did not become ready in time")


@contextmanager
def ollama(
    *,
    version: str | None = None,
    binary_cache_path: pathlib.Path,
) -> Iterator[_Ollama]:
    """Download an Ollama Windows CLI release and yield an Ollama handle.

    *version* is the Ollama release tag version (e.g., "0.17.7"). The archive is
    downloaded from the GitHub releases page if it does not already exist in
    *binary_cache_path*. The CLI zip archive `ollama-windows-amd64.zip` is
    fetched and the full folder structure is extracted into a versioned
    directory inside *binary_cache_path* and used from there.
    """
    if sys.platform != "win32":
        raise RuntimeError("Only implemented on Windows")

    if version is None:
        version = _DEFAULT_VERSION

    if version not in _KNOWN_VERSIONS:
        known = ", ".join(_KNOWN_VERSIONS)
        raise ValueError(
            "Unknown Ollama version '{}'; known versions: {}".format(
                version,
                known,
            )
        )

    dir_name = "ollama_{}".format(version.replace(".", "_"))
    version_dir = binary_cache_path / dir_name

    if not version_dir.exists():
        version_dir.mkdir(parents=True, exist_ok=True)

        url = _OLLAMA_URL_TEMPLATE.format(version=version)
        response = cast(HTTPResponse, urllib.request.urlopen(url))
        with response:
            zip_bytes: bytes = response.read()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(version_dir)

    exe_path = version_dir / "ollama.exe"
    if not exe_path.exists():
        raise RuntimeError(
            "Ollama executable 'ollama.exe' not found in '{}'".format(version_dir)
        )

    yield _Ollama(version=version, path=exe_path)


@contextmanager
def ollama_client(
    *,
    version: str | None = None,
    binary_cache_path: pathlib.Path,
    show_window: bool = False,
) -> Iterator[_ollama_client.Client]:
    """Provide an Ollama Python client with a running local server.

    Starts Ollama server in background and yields a configured
    :class:`ollama.Client` instance connected to default local host.
    Set *show_window* to True to allow a visible console window.
    """
    with ollama(version=version, binary_cache_path=binary_cache_path) as ollama_binary:
        with ollama_binary.lock():
            running = False

            # First check whether a process is already running.
            pid = ollama_binary.pid
            if pid is not None and pid.create_time is not None:
                try:
                    proc = psutil.Process(pid.pid)
                    running = (
                        proc.is_running()
                        and proc.status() != psutil.STATUS_ZOMBIE
                        and proc.create_time() == pid.create_time
                    )
                except psutil.Error:
                    running = False

            # If needed, start the server.
            if not running:
                ollama_binary.reset_state()

                stdout = None if show_window else subprocess.DEVNULL
                stderr = None if show_window else subprocess.DEVNULL
                creation_flags = subprocess.CREATE_NEW_CONSOLE if show_window else 0

                server_process = subprocess.Popen(
                    [str(ollama_binary.binary_path), "serve"],
                    stdout=stdout,
                    stderr=stderr,
                    creationflags=creation_flags,
                )
                ollama_binary.set_pid(
                    _PidWithCreateTime(
                        pid=server_process.pid,
                        create_time=psutil.Process(server_process.pid).create_time(),
                    )
                )

            # Increment the refcount.
            ollama_binary.set_refcount(ollama_binary.refcount + 1)

        try:
            # Wait until the server is listening.
            _wait_until_listening()

            # Create the client.
            client = _ollama_client.Client()
            yield client
        finally:
            with ollama_binary.lock():
                ollama_binary.set_refcount(ollama_binary.refcount - 1)

                if ollama_binary.refcount <= 0:
                    pid = ollama_binary.pid
                    if pid is not None:
                        _terminate_pid(pid=pid)
                    ollama_binary.reset_state()
