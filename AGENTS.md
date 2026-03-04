# Project Rules

## Development Environment

On Windows, this project uses the Python Install Manager.
- Example: `py --version`.

This project uses Poetry for dependency management and virtual environments.
- Example: `poetry run <command>`.
- On Windows, full example: `py -m poetry run <command>`.

This project uses Invoke for common development tasks.
- Example: `invoke format`.
- On Windows, full example: `py -m poetry run invoke format`.

Use Invoke to list available tasks.
- Example: `invoke -l`.
- On Windows, full example: `py -m poetry run invoke -l`.

## Style and Workflow Rules

Ensure new Cursor rules are always added here.

@.cursor/rules/file-operations.mdc
@.cursor/rules/style-batch.mdc
@.cursor/rules/style-comments.mdc
@.cursor/rules/style-python.mdc
@.cursor/rules/style-tests-python.mdc
