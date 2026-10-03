"""Invoke tasks for this project."""

import pathlib

import colorama
from invoke.collection import Collection

import fogies.tasks.access_key
import fogies.tasks.format
import fogies.tasks.lint
import fogies.tasks.poetry
import fogies.tasks.test
from fogies.tools.aws_environ import AwsEnvironContextManager, aws_environ_from_config
from tasks.paths import (
    SECRETS_AWS_PATH,
    SECRETS_POETRY_PATH,
    STAGING_BINARY_CACHE_PATH,
)

# Stand-in until a dedicated admin profile exists.
_ACCESS_KEY_PROFILE = "probe"


def _aws_environ_factory() -> AwsEnvironContextManager:
    """Build a fresh AWS environment for the access-key profile.

    A fresh instance per call: get_collection() shares this factory across
    five tasks, and a context manager built by @contextlib.contextmanager can
    only be entered once.
    """
    return aws_environ_from_config(
        config_path=SECRETS_AWS_PATH,
        profile_name=_ACCESS_KEY_PROFILE,
        raise_if_env_exists=False,
    )


# Root namespace for tasks.
namespace: Collection = Collection()

# Enable color output.
colorama.init()

# Tasks in the root collection.
namespace.add_task(
    fogies.tasks.format.get_task_format(
        fmt_black=True,
        fmt_isort=True,
        fmt_terraform=True,
        terraform_binary_cache_path=STAGING_BINARY_CACHE_PATH,
    )
)
namespace.add_task(fogies.tasks.lint.get_task_lint())
namespace.add_collection(
    fogies.tasks.poetry.get_collection(secrets_poetry_path=SECRETS_POETRY_PATH)
)
namespace.add_collection(
    fogies.tasks.access_key.get_collection(
        collection_name="access-key", aws_environ_factory=_aws_environ_factory
    )
)

# A collection for subsets of tests.
_task_all = fogies.tasks.test.get_task_test()
_task_integration = fogies.tasks.test.get_task_test(
    tests_path=pathlib.Path("tests/integration")
)
_task_terraform = fogies.tasks.test.get_task_test(
    tests_path=pathlib.Path("tests/terraform")
)
_task_unit = fogies.tasks.test.get_task_test(tests_path=pathlib.Path("tests/unit"))

_collection_tests = Collection("test")
_collection_tests.add_task(_task_all, name="all")
_collection_tests.add_task(_task_integration, name="integration")
_collection_tests.add_task(_task_terraform, name="terraform")
_collection_tests.add_task(_task_unit, name="unit")
namespace.add_collection(_collection_tests)
