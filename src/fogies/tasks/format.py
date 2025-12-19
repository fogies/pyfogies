"""
Task for applying code formatting.
"""

from invoke import Collection, task


class FormatTasks:
    """
    Tasks for applying code formatting.
    """

    @task(name="format")
    def task_format(context):
        """
        Apply code formatting.
        """

        context.run(
            command=" ".join(
                [
                    "black",
                    ".",
                ]
            ),
        )

    def get_collection(self) -> Collection:
        """
        Get a collection of tasks.
        """
        namespace = Collection("format")
        namespace.add_task(self.task_format)

        return namespace
