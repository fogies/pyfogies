"""Invoke tasks for this project."""

import colorama
from invoke.collection import Collection
from paths import PATH_SECRETS_POETRY

import fogies.tasks.format
import fogies.tasks.lint
import fogies.tasks.poetry
import fogies.tasks.test

# Root namespace for tasks.
namespace: Collection = Collection()

# Enable color output.
colorama.init()

# Tasks in the root collection.
namespace.add_task(fogies.tasks.format.get_task_format())
namespace.add_task(fogies.tasks.lint.get_task_lint())
namespace.add_collection(
    fogies.tasks.poetry.get_collection(path_secrets_poetry=PATH_SECRETS_POETRY)
)

# A collection for subsets of tests.
_task_all = fogies.tasks.test.get_task_test()
_task_integration = fogies.tasks.test.get_task_test("tests/integration")
_task_terraform = fogies.tasks.test.get_task_test("tests/terraform")
_task_tools = fogies.tasks.test.get_task_test("tests/tools")
_task_unit = fogies.tasks.test.get_task_test("tests/unit")

_collection_tests = Collection("test")
_collection_tests.add_task(_task_all, name="all")
_collection_tests.add_task(_task_integration, name="integration")
_collection_tests.add_task(_task_terraform, name="terraform")
_collection_tests.add_task(_task_tools, name="tools")
_collection_tests.add_task(_task_unit, name="unit")
namespace.add_collection(_collection_tests)
