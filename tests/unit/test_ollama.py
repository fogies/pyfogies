"""Unit tests for Ollama helpers."""

import psutil
import pytest
from paths import PATH_STAGING_BINARY_CACHE

from fogies.tools.ollama import ollama, ollama_client


def test_ollama_lock_context() -> None:
    """State access without the lock raises AssertionError."""
    with ollama(binary_cache_path=PATH_STAGING_BINARY_CACHE) as ol:
        with pytest.raises(AssertionError):
            _ = ol.pid
        with pytest.raises(AssertionError):
            _ = ol.refcount

        with ol.lock():
            _ = ol.pid
            _ = ol.refcount


def test_ollama_refcount_management() -> None:
    """Test ollama_client increments and decrements refcount."""
    with ollama(binary_cache_path=PATH_STAGING_BINARY_CACHE) as ol:
        with ol.lock():
            initial_refcount = ol.refcount
            started_pid = None

            with ollama_client(binary_cache_path=PATH_STAGING_BINARY_CACHE):
                assert ol.refcount == initial_refcount + 1
                if initial_refcount == 0:
                    started_pid = ol.pid
                    assert started_pid is not None

                    started_process = psutil.Process(started_pid.pid)
                    assert started_process.is_running()
                    assert started_process.status() != psutil.STATUS_ZOMBIE

                with ollama_client(binary_cache_path=PATH_STAGING_BINARY_CACHE):
                    assert ol.refcount == initial_refcount + 2

                assert ol.refcount == initial_refcount + 1

            assert ol.refcount == initial_refcount

        if initial_refcount == 0:
            assert started_pid is not None
            try:
                process = psutil.Process(started_pid.pid)
                assert not (
                    process.is_running()
                    and process.create_time() == started_pid.create_time
                )
            except psutil.Error:
                pass


def test_ollama_client_basic_query() -> None:
    """Test ollama_client can handle a small multi-turn sequence."""
    model = "llama3.1:8b"

    with ollama_client(
        binary_cache_path=PATH_STAGING_BINARY_CACHE, show_window=True
    ) as client:
        # Pull the model (will no-op if already present).
        _ = client.pull(model)

        first_response = client.chat(  # pyright: ignore[reportUnknownMemberType]
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Pick a number between 1 and 10.\n"
                        + "Reply with only a single numeric response, not a word.\n"
                    ),
                }
            ],
            stream=False,
        )
        first_number_text = first_response.message.content
        assert isinstance(first_number_text, str)
        first_number = int(first_number_text.strip())
        assert 1 <= first_number <= 10

        second_response = client.chat(  # pyright: ignore[reportUnknownMemberType]
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Pick a number between 1 and 10.\n"
                        + "Reply with only a single numeric response, not a word.\n"
                    ),
                }
            ],
            stream=False,
        )
        second_number_text = second_response.message.content
        assert isinstance(second_number_text, str)
        second_number = int(second_number_text.strip())
        assert 1 <= second_number <= 10

        response = client.chat(  # pyright: ignore[reportUnknownMemberType]
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Take these two numbers and give their sum.\n"
                        + "First: {}\n".format(first_number_text)
                        + "Second: {}\n".format(second_number_text)
                        + "Reply with only a single numeric response, not a word.\n"
                    ),
                }
            ],
            stream=False,
        )
        answer = response.message.content
        assert isinstance(answer, str)
        answer_sum = int(answer.strip())
        assert answer_sum == first_number + second_number
