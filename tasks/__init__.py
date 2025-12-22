"""Invoke tasks for this project."""

import colorama
from invoke.collection import Collection

import fogies.tasks.format
import fogies.tasks.lint
import fogies.tasks.test

# Root namespace for tasks.
namespace: Collection = Collection()

# Enable color output.
colorama.init()

# TODO: This still feels messy, will need a bettery way to compose tasks as more develop.
# Type errors ignored until we reorganize task composition.
namespace.add_task(
    task=fogies.tasks.format.FormatTasks().get_collection()[
        "format"
    ],  # pyright: ignore[reportAny]
)
namespace.add_task(
    task=fogies.tasks.lint.LintTasks().get_collection()[
        "lint"
    ],  # pyright: ignore[reportAny]
)
namespace.add_task(
    task=fogies.tasks.test.TestTasks().get_collection()[
        "test"
    ],  # pyright: ignore[reportAny]
)
