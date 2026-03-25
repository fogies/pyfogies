import io
import pathlib
import shutil
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
    create_time_seconds: int


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

        text = pid_path.read_text(encoding="utf-8")
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


def _create_time_seconds(create_time: float) -> int:
    """Convert process create_time to truncated integer seconds."""
    return int(create_time)


def _terminate_pid(*, pid: _PidWithCreateTime) -> None:
    try:
        process = psutil.Process(pid.pid)

        # If the process has been restarted, the pid was reused, do not terminate it.
        process_create_time_seconds = _create_time_seconds(process.create_time())
        if process_create_time_seconds != pid.create_time_seconds:
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
    pid: _PidWithCreateTime,
    timeout: float = _OLLAMA_LISTEN_PROBE_WAIT_TIMEOUT,
) -> None:
    end = time.time() + timeout
    while time.time() < end:
        try:
            proc = psutil.Process(pid.pid)
            alive = (
                proc.is_running()
                and proc.status() != psutil.STATUS_ZOMBIE
                and _create_time_seconds(proc.create_time()) == pid.create_time_seconds
            )
        except psutil.Error:
            alive = False
        if not alive:
            raise RuntimeError("Ollama server process exited before becoming ready")
        try:
            with socket.create_connection(
                _OLLAMA_LISTEN_ADDRESS,
                timeout=_OLLAMA_LISTEN_PROBE_TIMEOUT,
            ):
                return
        except OSError:
            pass
        time.sleep(_OLLAMA_LISTEN_POLL_INTERVAL)
    raise TimeoutError("Ollama server did not become ready")


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
    exe_path = version_dir / "ollama.exe"

    if not exe_path.exists():
        version_dir.mkdir(parents=True, exist_ok=True)
        try:
            url = _OLLAMA_URL_TEMPLATE.format(version=version)
            response = cast(HTTPResponse, urllib.request.urlopen(url))
            with response:
                zip_bytes: bytes = response.read()

            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                zf.extractall(version_dir)
        except Exception:
            shutil.rmtree(version_dir, ignore_errors=True)
            raise

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
            # First check whether a process is already running.
            running = False
            if ollama_binary.pid is not None:
                try:
                    proc = psutil.Process(ollama_binary.pid.pid)
                    running = (
                        proc.is_running()
                        and proc.status() != psutil.STATUS_ZOMBIE
                        and _create_time_seconds(proc.create_time())
                        == ollama_binary.pid.create_time_seconds
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
                        create_time_seconds=_create_time_seconds(
                            psutil.Process(server_process.pid).create_time()
                        ),
                    )
                )

            # We now believe it is running.
            assert ollama_binary.pid is not None

            # Increment the refcount.
            ollama_binary.set_refcount(ollama_binary.refcount + 1)

            # Wait until the server is listening.
            _wait_until_listening(pid=ollama_binary.pid)

        try:
            # Create the client.
            client = _ollama_client.Client()
            yield client
        finally:
            with ollama_binary.lock():
                ollama_binary.set_refcount(ollama_binary.refcount - 1)

                if ollama_binary.refcount == 0:
                    _terminate_pid(pid=ollama_binary.pid)
                    ollama_binary.reset_state()
