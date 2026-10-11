"""Age secret keys, which encrypt what claude-sync uploads.

An age secret key is a string like AGE-SECRET-KEY-1...: see
<https://github.com/FiloSottile/age>. pyrage, which binds to a Rust
implementation of age, creates and checks them. It ships no type stubs, so the
little of it that is used is given types here and nowhere else.
"""

from typing import Protocol, cast

import pyrage  # pyright: ignore[reportMissingTypeStubs]


class _IdentityFactory(Protocol):
    """The parts of pyrage's x25519 Identity class that are used."""

    def generate(self) -> object: ...

    def from_str(self, value: str) -> object: ...


_IDENTITY = cast(
    _IdentityFactory,
    pyrage.x25519.Identity,  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
)

_IDENTITY_ERROR = cast(
    type[Exception],
    pyrage.IdentityError,  # pyright: ignore[reportAttributeAccessIssue]
)


def generate_age_key() -> str:
    """Return a new, random age secret key."""
    return str(_IDENTITY.generate())


def validate_age_key(value: str) -> str:
    """Return value, if it is an age secret key.

    Raises ValueError if it is not, including a key with a mistyped character,
    since the checksum is checked.
    """
    try:
        _ = _IDENTITY.from_str(value)
    except _IDENTITY_ERROR as exc:
        raise ValueError("Not an age secret key") from exc
    return value
