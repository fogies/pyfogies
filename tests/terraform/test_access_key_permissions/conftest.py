"""Fixtures shared by the access-key-permissions tests: a disposable IAM user."""

import uuid
from collections.abc import Iterator

import pytest

import fogies.aws_access_key as aws_access_key
from fogies.tools.aws_environ import AwsEnviron, AwsProfile

# Shared by the access_key_username fixture below and by
# _delete_stale_access_key_users, which sweeps by this prefix since it
# can't know a prior run's exact suffix.
_TEST_USERNAME_PREFIX = "pyfogies-test-access-key-permissions-"


def _delete_user_and_keys(
    *, username: str, protected_key_id: str, protected_username: str
) -> None:
    """Delete username and all its keys, if it exists.

    protected_key_id/protected_username guard the currently-authenticated
    admin key/user, so a coincidental name collision can never delete them.
    """
    try:
        keys = aws_access_key.get_keys(username=username)
    except ValueError:
        return
    for key in (keys.current, keys.previous):
        if key is not None:
            aws_access_key.delete_key(
                username=username,
                key_id=key.key_id,
                protected_key_ids={protected_key_id},
            )
    aws_access_key.delete_user(
        username=username, protected_usernames={protected_username}
    )


def _delete_stale_access_key_users(
    *, protected_key_id: str, protected_username: str
) -> None:
    """Delete any leftover test users from prior runs that crashed before cleanup.

    username is unique per run, so an exact-name check would never find a
    prior run's leftover -- sweep by the shared prefix instead.
    """
    for user in aws_access_key.list_users():
        if user.username.startswith(_TEST_USERNAME_PREFIX):
            _delete_user_and_keys(
                username=user.username,
                protected_key_id=protected_key_id,
                protected_username=protected_username,
            )


@pytest.fixture(scope="module")
def access_key_username() -> str:
    """A fresh, never-before-used username for this test run.

    Unique per run: some AWS-side authorization caching appears to key on
    the ARN string rather than the user's underlying unique ID, so
    recreating the same name repeatedly (as happens across many local test
    runs) can leave a stale "no policy" result that blocks a fresh grant
    for an unpredictably long time.
    """
    return _TEST_USERNAME_PREFIX + uuid.uuid4().hex[:8]


@pytest.fixture(scope="module")
def access_key_profile(
    access_key_username: str, pyfogies_test_aws_environ: AwsEnviron
) -> Iterator[AwsProfile]:
    """Create a disposable IAM user with an access key; delete both on teardown.

    Sweeps up any leftover users from prior runs that crashed before
    cleanup, since those would sit under a different run's suffix forever
    otherwise.
    """
    _delete_stale_access_key_users(
        protected_key_id=pyfogies_test_aws_environ.aws_access_key_id,
        protected_username=pyfogies_test_aws_environ.username,
    )
    profile = aws_access_key.create_user(username=access_key_username)
    try:
        yield profile
    finally:
        _delete_user_and_keys(
            username=access_key_username,
            protected_key_id=pyfogies_test_aws_environ.aws_access_key_id,
            protected_username=pyfogies_test_aws_environ.username,
        )
