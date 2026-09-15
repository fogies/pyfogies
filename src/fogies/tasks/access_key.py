"""Tasks for managing IAM users and access keys."""

from __future__ import annotations

import contextlib
import getpass
from collections.abc import Callable, Generator
from typing import cast

from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task

import fogies.aws_access_key as aws_access_key
from fogies.tools.aws_environ import (
    AwsEnvironContextManager,
    AwsProfile,
    aws_environ_from_profile,
)
from fogies.typing import boto_client_sts

# A factory rather than a pre-built context manager: get_collection() shares
# this across five tasks, and a context manager built by @contextlib.
# contextmanager can only be entered once, so each task must build its own
# fresh instance at run time. Mirrors the _aws_environ_factory() pattern used
# by consumers of these tasks (see e.g. fogies-infrastructure's tasks/__init__.py).
AwsEnvironFactory = Callable[[], AwsEnvironContextManager]


def _prompt_admin_credentials() -> tuple[str, str]:
    """Prompt for admin credentials interactively; credentials are never written anywhere."""
    access_key_id = input("Admin Access Key ID: ").strip()
    secret_access_key = getpass.getpass("Admin Secret Access Key: ").strip()
    return access_key_id, secret_access_key


@contextlib.contextmanager
def _resolve_admin_environ(
    *, aws_environ_factory: AwsEnvironFactory | None, prompt: bool
) -> Generator[str]:
    """Enter the configured AWS environment, or prompt for admin credentials.

    Prompts if aws_environ_factory is None, or if prompt is True (e.g. to use
    different/elevated credentials for a single run). Prompted credentials
    are never written anywhere. Yields the active access key ID.
    """
    if aws_environ_factory is not None and not prompt:
        with aws_environ_factory() as env:
            yield env.aws_access_key_id
        return

    access_key_id, secret_access_key = _prompt_admin_credentials()
    profile = AwsProfile(
        name="prompt-admin",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )
    # try/except wraps only entering the context manager (where validation
    # happens), not the yield below — catching ValueError around the yield
    # too would risk mis-catching an unrelated error raised by the task body.
    with contextlib.ExitStack() as stack:
        try:
            env = stack.enter_context(
                aws_environ_from_profile(profile=profile, raise_if_exists=False)
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        yield env.aws_access_key_id


def _caller_username() -> str:
    """Return the IAM username that owns the active credentials, via STS."""
    arn = boto_client_sts().get_caller_identity()["Arn"]
    # ARN format for IAM users: arn:aws:iam::123456789012:user/username
    return arn.split("/")[-1]


def _print_toml_block(*, profile: AwsProfile) -> None:
    """Print a TOML block suitable for pasting into aws.toml."""
    print()
    print("[{}]".format(profile.name))
    print('aws_access_key_id = "{}"'.format(profile.aws_access_key_id))
    print('aws_secret_access_key = "{}"'.format(profile.aws_secret_access_key))


def _print_user_key_overview(
    *, username: str, keys: aws_access_key.IamAccessKeys
) -> None:
    """Print an IAM user's key overview: current/previous key details, or a no-keys note.

    Shared by `list` (once per user) and `delete-key`'s confirmation prompt
    (for the one user being acted on), so both show the same information.
    """
    print(username)
    for label, key in (("current", keys.current), ("previous", keys.previous)):
        if key is None:
            continue
        created_str = key.created.strftime("%Y-%m-%d") if key.created else "unknown"
        last_used_str = key.last_used.strftime("%Y-%m-%d") if key.last_used else "never"
        print(
            "  {} {} | {} | created {} | last used {}".format(
                label, key.key_id, key.status, created_str, last_used_str
            )
        )
    if keys.current is None:
        print("  (no access keys)")


def get_task_create(
    *, aws_environ_factory: AwsEnvironFactory | None = None
) -> Task[Callable[..., None]]:
    @task(name="create")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_create(context: Context, *, prompt: bool = False, username: str) -> None:
        """
        Create an IAM user and an associated access key.

        Flags:
          --prompt    Prompt for admin credentials.
          --username  IAM username.
        """
        _ = context
        with _resolve_admin_environ(
            aws_environ_factory=aws_environ_factory, prompt=prompt
        ):
            new_profile = aws_access_key.create_user(username=username)
        print("Created IAM user '{}'.".format(username))
        print("Created access key {}.".format(new_profile.aws_access_key_id))
        _print_toml_block(profile=new_profile)

    return cast(Task[Callable[..., None]], task_create)


def get_task_delete(
    *, aws_environ_factory: AwsEnvironFactory | None = None
) -> Task[Callable[..., None]]:
    @task(name="delete")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_delete(context: Context, *, prompt: bool = False, username: str) -> None:
        """
        Delete an IAM user with no remaining access keys.

        Flags:
          --prompt    Prompt for admin credentials.
          --username  IAM username.
        """
        _ = context
        with _resolve_admin_environ(
            aws_environ_factory=aws_environ_factory, prompt=prompt
        ):
            protected_username = _caller_username()
            confirm = (
                input("Delete IAM user '{}'? [y/N] ".format(username)).strip().lower()
            )
            if confirm != "y":
                print("Aborted.")
                return
            aws_access_key.delete_user(
                username=username,
                protected_usernames={protected_username},
            )
        print("Deleted IAM user '{}'.".format(username))

    return cast(Task[Callable[..., None]], task_delete)


def get_task_delete_key(
    *, aws_environ_factory: AwsEnvironFactory | None = None
) -> Task[Callable[..., None]]:
    @task(name="delete-key")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_delete_key(
        context: Context, *, prompt: bool = False, username: str
    ) -> None:
        """
        Delete the oldest access key for an IAM user.

        Flags:
          --prompt    Prompt for admin credentials.
          --username  IAM username.
        """
        _ = context
        with _resolve_admin_environ(
            aws_environ_factory=aws_environ_factory, prompt=prompt
        ) as admin_key_id:
            keys = aws_access_key.get_keys(username=username)
            target = keys.previous or keys.current
            if target is None:
                raise SystemExit("IAM user '{}' has no access keys.".format(username))
            key_id = target.key_id
            _print_user_key_overview(username=username, keys=keys)
            print()
            if keys.previous is None:
                print(
                    "WARNING: This is the only key. Deleting it will revoke all access."
                )
                print()
            confirm = input("Delete key {}? [y/N] ".format(key_id)).strip().lower()
            if confirm != "y":
                print("Aborted.")
                return
            aws_access_key.delete_key(
                username=username,
                key_id=key_id,
                protected_key_ids={admin_key_id},
            )
        print("Deleted key {}.".format(key_id))

    return cast(Task[Callable[..., None]], task_delete_key)


def get_task_list(
    *, aws_environ_factory: AwsEnvironFactory | None = None
) -> Task[Callable[..., None]]:
    @task(name="list")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_list(context: Context, *, prompt: bool = False) -> None:
        """
        List all IAM users and their access keys.

        Flags:
          --prompt  Prompt for admin credentials.
        """
        _ = context
        with _resolve_admin_environ(
            aws_environ_factory=aws_environ_factory, prompt=prompt
        ):
            users = aws_access_key.list_users()
        if not users:
            print("No IAM users found.")
            return
        for index, user in enumerate(users):
            if index > 0:
                print()
            _print_user_key_overview(username=user.username, keys=user.keys)

    return cast(Task[Callable[..., None]], task_list)


def get_task_rotate_key(
    *, aws_environ_factory: AwsEnvironFactory | None = None
) -> Task[Callable[..., None]]:
    @task(name="rotate-key")  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_rotate_key(
        context: Context, *, prompt: bool = False, username: str
    ) -> None:
        """
        Add a new access key to an existing IAM user.

        Flags:
          --prompt    Prompt for admin credentials instead of using the configured AWS environment.
          --username  IAM username to rotate a key for.
        """
        _ = context
        with _resolve_admin_environ(
            aws_environ_factory=aws_environ_factory, prompt=prompt
        ) as admin_key_id:
            keys = aws_access_key.get_keys(username=username)
            if keys.previous is not None:
                _print_user_key_overview(username=username, keys=keys)
                print()
                confirm = (
                    input("Delete key {}? [y/N] ".format(keys.previous.key_id))
                    .strip()
                    .lower()
                )
                if confirm != "y":
                    print("Aborted.")
                    return
            new_profile = aws_access_key.rotate_key(
                username=username,
                protected_key_ids={admin_key_id},
            )
        print("Created access key {}.".format(new_profile.aws_access_key_id))
        _print_toml_block(profile=new_profile)

    return cast(Task[Callable[..., None]], task_rotate_key)


def get_collection(
    *, aws_environ_factory: AwsEnvironFactory | None = None
) -> Collection:
    """Get a collection of tasks for managing IAM users and access keys."""
    collection = Collection("access-key")
    collection.add_task(get_task_create(aws_environ_factory=aws_environ_factory))
    collection.add_task(get_task_delete(aws_environ_factory=aws_environ_factory))
    collection.add_task(get_task_delete_key(aws_environ_factory=aws_environ_factory))
    collection.add_task(get_task_list(aws_environ_factory=aws_environ_factory))
    collection.add_task(get_task_rotate_key(aws_environ_factory=aws_environ_factory))
    return collection
