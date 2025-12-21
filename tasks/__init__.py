"""Invoke tasks for this project."""

import colorama
from invoke import Collection

import fogies.tasks.format
import fogies.tasks.test

# Root namespace for tasks.
namespace: Collection = Collection()

# Enable color output.
colorama.init()

# TODO: This still feels messy, will need a bettery way to compose tasks as more develop.
namespace.add_task(fogies.tasks.format.FormatTasks().get_collection()["format"])
namespace.add_task(fogies.tasks.test.TestTasks().get_collection()["test"])
