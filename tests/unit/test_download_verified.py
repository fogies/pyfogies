"""Tests for fogies.download_verified."""

import hashlib
import http.server
import socket
import threading
from collections.abc import Iterator
from typing import cast, override

import pytest

from fogies.download_verified import download_verified

_CONTENT = b"test_download_content"


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(_CONTENT)))
        self.end_headers()
        _ = self.wfile.write(_CONTENT)

    @override
    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def server_url() -> Iterator[str]:
    """Serve _CONTENT from a real local HTTP server for the module."""
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{}/file".format(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_download_verified_returns_content(server_url: str) -> None:
    """Content is returned when the checksum matches, regardless of case."""
    sha256 = hashlib.sha256(_CONTENT).hexdigest()

    assert download_verified(url=server_url, sha256=sha256) == _CONTENT
    assert download_verified(url=server_url, sha256=sha256.upper()) == _CONTENT


def test_download_verified_raises_on_mismatch(server_url: str) -> None:
    """A checksum mismatch raises ValueError and returns nothing."""
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        _ = download_verified(url=server_url, sha256="0" * 64)


def test_download_verified_times_out() -> None:
    """A server that accepts the connection but never answers fails, not hangs."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = cast(int, listener.getsockname()[1])

        with pytest.raises(TimeoutError):
            _ = download_verified(
                url="http://127.0.0.1:{}/file".format(port),
                sha256="0" * 64,
                timeout_seconds=0.5,
            )
