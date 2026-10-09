"""Test creating and checking age secret keys."""

import pytest

from fogies.age_key import generate_age_key, validate_age_key

# A valid age secret key, fixed so that it can be altered in the tests below.
_KEY = "AGE-SECRET-KEY-1QQQSYQCYQ5RQWZQFPG9SCRGWPUGPZYSNZS23V9CCRYDPK8QARC0SWRYDWG"


def test_generate_age_key_makes_a_valid_key() -> None:
    key = generate_age_key()

    assert key.startswith("AGE-SECRET-KEY-1")
    assert validate_age_key(key) == key


def test_generate_age_key_is_random() -> None:
    assert generate_age_key() != generate_age_key()


def test_validate_age_key_accepts_a_key() -> None:
    assert validate_age_key(_KEY) == _KEY


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not a key",
        # A public key, which age also writes, is not a secret key.
        "age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p",
        # A mistyped character fails the checksum.
        _KEY[:-1] + "A",
    ],
    ids=["empty", "gibberish", "public key", "mistyped"],
)
def test_validate_age_key_rejects_what_is_not_a_key(value: str) -> None:
    with pytest.raises(ValueError):
        _ = validate_age_key(value)
