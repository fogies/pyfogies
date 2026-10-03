"""Download a file over HTTP, verifying its SHA-256 checksum."""

import hashlib
import urllib.request
from http.client import HTTPResponse
from typing import cast

# Timeout for each blocking socket operation of a download, in seconds.
DOWNLOAD_VERIFIED_TIMEOUT_SECONDS = 300.0


def download_verified(
    *,
    url: str,
    sha256: str,
    timeout_seconds: float = DOWNLOAD_VERIFIED_TIMEOUT_SECONDS,
) -> bytes:
    """Download *url* and return its content, if its SHA-256 matches *sha256*.

    *sha256* is the expected checksum as a hexadecimal string, taken from the
    publisher and recorded alongside the pinned version being downloaded.
    *timeout_seconds* applies to each blocking socket operation, not to the
    download as a whole, so a stalled connection fails instead of hanging.
    Raises ValueError if the checksum does not match, returning nothing.
    """
    response = cast(HTTPResponse, urllib.request.urlopen(url, timeout=timeout_seconds))
    with response:
        content: bytes = response.read()

    actual_sha256 = hashlib.sha256(content).hexdigest()
    if actual_sha256 != sha256.lower():
        raise ValueError(
            "SHA-256 mismatch for '{}': expected {}, got {}".format(
                url,
                sha256.lower(),
                actual_sha256,
            )
        )
    return content
