"""Invoke tasks for this project."""

from pathlib import Path

import colorama
from invoke.collection import Collection

import fogies.tasks.format
import fogies.tasks.lint
import fogies.tasks.poetry
import fogies.tasks.test

# Path to the Poetry secrets configuration file.
PATH_SECRETS_POETRY = Path("secrets", "poetry.toml")

# Root namespace for tasks.
namespace: Collection = Collection()

# Enable color output.
colorama.init()

# Add tasks to the root namespace.
namespace.add_task(fogies.tasks.format.get_task_format())
namespace.add_task(fogies.tasks.lint.get_task_lint())
namespace.add_task(fogies.tasks.test.get_task_test())
namespace.add_collection(
    fogies.tasks.poetry.get_collection(path_secrets_poetry=PATH_SECRETS_POETRY)
)
