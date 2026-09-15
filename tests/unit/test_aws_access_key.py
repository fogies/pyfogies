"""Integration tests for fogies.aws_access_key against real AWS."""

from collections.abc import Iterator

import pytest

import fogies.aws_access_key as aws_access_key
from fogies.tools.aws_environ import AwsEnviron, AwsProfile

_TEST_USERNAME = "pyfogies-test-aws-access-key"
_NONEXISTENT_USERNAME = "pyfogies-test-aws-access-key-nonexistent"


def _delete_test_user_if_exists(pyfogies_test_aws_environ: AwsEnviron) -> None:
    """Delete the test user and all its keys if it exists."""
    try:
        keys = aws_access_key.get_keys(username=_TEST_USERNAME)
    except ValueError:
        return
    for key in (keys.current, keys.previous):
        if key is not None:
            aws_access_key.delete_key(
                username=_TEST_USERNAME,
                key_id=key.key_id,
                protected_key_ids={pyfogies_test_aws_environ.aws_access_key_id},
            )
    aws_access_key.delete_user(username=_TEST_USERNAME, protected_usernames=set())


@pytest.fixture(scope="module")
def test_profile(pyfogies_test_aws_environ: AwsEnviron) -> Iterator[AwsProfile]:
    """Create a single test IAM user for the module; yield its initial profile; clean up on teardown."""
    _delete_test_user_if_exists(pyfogies_test_aws_environ)
    initial_profile = aws_access_key.create_user(username=_TEST_USERNAME)
    try:
        yield initial_profile
    finally:
        _delete_test_user_if_exists(pyfogies_test_aws_environ)


@pytest.fixture
def test_profile_known_state(
    test_profile: AwsProfile, pyfogies_test_aws_environ: AwsEnviron
) -> AwsProfile:
    """Reset the test user to a known state: one current key, no previous key.

    Minimizes AWS API calls — each call adds latency. Recreates the user if a
    previous test deleted it. Skips key recreation if the user already has
    exactly one key.
    """
    _ = test_profile
    try:
        keys = aws_access_key.get_keys(username=_TEST_USERNAME)
    except ValueError:
        return aws_access_key.create_user(username=_TEST_USERNAME)
    if keys.previous is not None:
        # Deleting previous leaves current intact — no need to re-fetch.
        aws_access_key.delete_key(
            username=_TEST_USERNAME,
            key_id=keys.previous.key_id,
            protected_key_ids={pyfogies_test_aws_environ.aws_access_key_id},
        )
    if keys.current is None:
        return aws_access_key.rotate_key(
            username=_TEST_USERNAME,
            protected_key_ids={pyfogies_test_aws_environ.aws_access_key_id},
        )
    return AwsProfile(
        name=_TEST_USERNAME,
        aws_access_key_id=keys.current.key_id,
        aws_secret_access_key="",
    )


def test_get_keys_raises_for_missing_user(
    pyfogies_test_aws_environ: AwsEnviron,
) -> None:
    """get_keys raises ValueError (not a raw botocore exception) for a nonexistent user."""
    _ = pyfogies_test_aws_environ
    with pytest.raises(ValueError, match="not found"):
        _ = aws_access_key.get_keys(username=_NONEXISTENT_USERNAME)


def test_delete_user_raises_for_missing_user(
    pyfogies_test_aws_environ: AwsEnviron,
) -> None:
    """delete_user raises ValueError (not a raw botocore exception) for a nonexistent user."""
    _ = pyfogies_test_aws_environ
    with pytest.raises(ValueError, match="not found"):
        aws_access_key.delete_user(
            username=_NONEXISTENT_USERNAME, protected_usernames=set()
        )


def test_create_user_raises_if_exists(test_profile: AwsProfile) -> None:
    """create_user raises ValueError if the user already exists."""
    _ = test_profile
    with pytest.raises(ValueError, match="already exists"):
        _ = aws_access_key.create_user(username=_TEST_USERNAME)


def test_create_user_creates_initial_key(test_profile: AwsProfile) -> None:
    """create_user returns an AwsProfile with credentials and a current key."""
    assert test_profile.aws_access_key_id.startswith("AKIA")
    assert len(test_profile.aws_secret_access_key) > 0

    keys = aws_access_key.get_keys(username=_TEST_USERNAME)
    assert keys.current is not None
    assert keys.previous is None


def test_list_users_includes_new_user(test_profile: AwsProfile) -> None:
    """list_users returns the test user."""
    _ = test_profile
    users = aws_access_key.list_users()
    assert any(u.username == _TEST_USERNAME for u in users)


def test_rotate_key_creates_new_current(
    pyfogies_test_aws_environ: AwsEnviron,
    test_profile_known_state: AwsProfile,
) -> None:
    """rotate_key creates a new current key; the original key becomes previous."""
    rotated = aws_access_key.rotate_key(
        username=_TEST_USERNAME,
        protected_key_ids={pyfogies_test_aws_environ.aws_access_key_id},
    )
    assert rotated.aws_access_key_id.startswith("AKIA")
    assert rotated.aws_access_key_id != test_profile_known_state.aws_access_key_id

    keys = aws_access_key.get_keys(username=_TEST_USERNAME)
    assert keys.current is not None
    assert keys.current.key_id == rotated.aws_access_key_id
    assert keys.previous is not None
    assert keys.previous.key_id == test_profile_known_state.aws_access_key_id


def test_rotate_key_deletes_existing_previous(
    pyfogies_test_aws_environ: AwsEnviron,
    test_profile_known_state: AwsProfile,
) -> None:
    """A second rotate deletes the existing previous key; second_rotate is current, first_rotate is previous."""
    first_rotate = aws_access_key.rotate_key(
        username=_TEST_USERNAME,
        protected_key_ids={pyfogies_test_aws_environ.aws_access_key_id},
    )

    keys = aws_access_key.get_keys(username=_TEST_USERNAME)
    assert keys.previous is not None
    assert keys.previous.key_id == test_profile_known_state.aws_access_key_id

    second_rotate = aws_access_key.rotate_key(
        username=_TEST_USERNAME,
        protected_key_ids={pyfogies_test_aws_environ.aws_access_key_id},
    )

    assert second_rotate.aws_access_key_id != first_rotate.aws_access_key_id
    assert second_rotate.aws_access_key_id != test_profile_known_state.aws_access_key_id

    keys = aws_access_key.get_keys(username=_TEST_USERNAME)
    assert keys.current is not None
    assert keys.current.key_id == second_rotate.aws_access_key_id
    assert keys.previous is not None
    assert keys.previous.key_id == first_rotate.aws_access_key_id


def test_delete_key_removes_key(
    pyfogies_test_aws_environ: AwsEnviron,
    test_profile_known_state: AwsProfile,
) -> None:
    """delete_key removes the specified key."""
    _ = test_profile_known_state
    _ = aws_access_key.rotate_key(
        username=_TEST_USERNAME,
        protected_key_ids={pyfogies_test_aws_environ.aws_access_key_id},
    )

    keys = aws_access_key.get_keys(username=_TEST_USERNAME)
    assert keys.previous is not None
    aws_access_key.delete_key(
        username=_TEST_USERNAME,
        key_id=keys.previous.key_id,
        protected_key_ids={pyfogies_test_aws_environ.aws_access_key_id},
    )

    keys = aws_access_key.get_keys(username=_TEST_USERNAME)
    assert keys.current is not None
    assert keys.previous is None


def test_delete_key_refuses_protected_key(
    pyfogies_test_aws_environ: AwsEnviron,
    test_profile_known_state: AwsProfile,
) -> None:
    """delete_key raises ValueError when asked to delete a protected key."""
    protected = {
        test_profile_known_state.aws_access_key_id,
        pyfogies_test_aws_environ.aws_access_key_id,
    }
    with pytest.raises(ValueError, match="protected key"):
        aws_access_key.delete_key(
            username=_TEST_USERNAME,
            key_id=test_profile_known_state.aws_access_key_id,
            protected_key_ids=protected,
        )


def test_delete_user_raises_if_has_keys(
    pyfogies_test_aws_environ: AwsEnviron,
    test_profile_known_state: AwsProfile,
) -> None:
    """delete_user raises ValueError when the user still has keys."""
    _ = test_profile_known_state
    with pytest.raises(ValueError, match="still has"):
        aws_access_key.delete_user(
            username=_TEST_USERNAME,
            protected_usernames={pyfogies_test_aws_environ.username},
        )


def test_delete_user_raises_if_protected(
    pyfogies_test_aws_environ: AwsEnviron,
    test_profile_known_state: AwsProfile,
) -> None:
    """delete_user raises ValueError when the username is protected."""
    aws_access_key.delete_key(
        username=_TEST_USERNAME,
        key_id=test_profile_known_state.aws_access_key_id,
        protected_key_ids={pyfogies_test_aws_environ.aws_access_key_id},
    )
    with pytest.raises(ValueError, match="protected IAM user"):
        aws_access_key.delete_user(
            username=_TEST_USERNAME,
            protected_usernames={_TEST_USERNAME, pyfogies_test_aws_environ.username},
        )


def test_delete_user_succeeds_after_keys_removed(
    pyfogies_test_aws_environ: AwsEnviron,
    test_profile_known_state: AwsProfile,
) -> None:
    """delete_user succeeds once all keys are gone."""
    aws_access_key.delete_key(
        username=_TEST_USERNAME,
        key_id=test_profile_known_state.aws_access_key_id,
        protected_key_ids={pyfogies_test_aws_environ.aws_access_key_id},
    )
    aws_access_key.delete_user(
        username=_TEST_USERNAME,
        protected_usernames={pyfogies_test_aws_environ.username},
    )

    users = aws_access_key.list_users()
    assert not any(u.username == _TEST_USERNAME for u in users)
