"""Tasks for the sessions that the Claude desktop app lists, and opening others in it.

The app lists only sessions it has a record of on this machine, as read by
fogies.tools.claude_desktop. A session synced here from another machine (e.g.,
by claude-sync) has a transcript but no record, so is not in the sidebar until it
is resumed in the app.
"""

import pathlib
from collections.abc import Callable
from typing import cast

from claude_agent_sdk import list_sessions
from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import Task, task

from fogies.tools.claude_code import claude_code
from fogies.tools.claude_desktop import (
    desktop_sessions,
    desktop_sessions_directory,
)
from fogies.tools.claude_sessions import describe_session, find_session_id

_NOT_FOUND = "The Claude desktop app's sessions were not found here ({}).".format


def get_task_sessions() -> Task[Callable[..., None]]:
    @task(
        name="sessions", auto_shortflags=False
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_sessions(context: Context) -> None:
        """
        List sessions on this machine, and whether the Claude desktop app lists them.
        """
        _ = context
        recorded = desktop_sessions()
        if recorded is None:
            raise ValueError(_NOT_FOUND(desktop_sessions_directory()))

        transcripts = list_sessions()
        for session in transcripts:
            record = recorded.get(session.session_id)
            if record is None:
                status = "not listed"
            else:
                status = "archived" if record.archived else "listed"
            print("{:<10}  {}".format(status, describe_session(session)))

        # Listed by the app, but with no transcript here, so not able to be opened.
        have = {session.session_id for session in transcripts}
        for record in recorded.values():
            if record.session_id not in have:
                print(
                    "{:<10}  {}  {}".format(
                        "no history", record.session_id, record.title or ""
                    )
                )

    return cast(Task[Callable[..., None]], task_sessions)


def get_task_resume(*, binary_cache_path: pathlib.Path) -> Task[Callable[..., None]]:
    @task(
        name="resume",
        auto_shortflags=False,
        help={
            "session_id": "Session to resume, from any part of its ID that is only in that one.",
            "all": "Resume every session that the app does not list, except those that ran in a directory that is not here.",
        },
    )  # pyright: ignore[reportUntypedFunctionDecorator]
    def task_resume(
        context: Context, session_id: str | None = None, all_: bool = False
    ) -> None:
        """
        Resume a session, or all that are not listed, in Claude desktop.
        """
        _ = context
        if (session_id is not None) == all_:
            raise ValueError("Give a session ID, or --all, and not both.")

        sessions = {session.session_id: session for session in list_sessions()}
        if all_:
            recorded = desktop_sessions()
            if recorded is None:
                # Without knowing what is listed, all would be every session.
                raise ValueError(_NOT_FOUND(desktop_sessions_directory()))
            # Archived sessions are recorded, so are not resumed.
            session_ids = [i for i in sessions if i not in recorded]
        else:
            assert session_id is not None
            session_ids = [find_session_id(list(sessions), session_id)]

        resumed = 0
        with claude_code(binary_cache_path=binary_cache_path) as cc:
            for resume_id in session_ids:
                cwd = sessions[resume_id].cwd
                if cwd is None:
                    problem = "has no recorded directory"
                elif not pathlib.Path(cwd).is_dir():
                    problem = "ran in '{}', which does not exist here".format(cwd)
                else:
                    problem = None

                if problem is not None:
                    # One session that is asked for is an error. Skipping a
                    # session is for when all of them are.
                    if not all_:
                        raise ValueError("Session '{}' {}".format(resume_id, problem))
                    print("Skipping {}, as it {}.".format(resume_id, problem))
                    continue

                assert cwd is not None
                print("Resuming {}.".format(resume_id))
                cc.resume_in_desktop(session_id=resume_id, cwd=pathlib.Path(cwd))
                resumed += 1

        if all_:
            print(
                "Resumed {} of {} sessions not listed.".format(
                    resumed, len(session_ids)
                )
            )

    return cast(Task[Callable[..., None]], task_resume)


def get_collection(
    *,
    collection_name: str,
    binary_cache_path: pathlib.Path,
) -> Collection:
    """Get a collection of tasks for the sessions that the Claude desktop app lists."""
    collection = Collection(collection_name)
    collection.add_task(get_task_resume(binary_cache_path=binary_cache_path))
    collection.add_task(get_task_sessions())
    return collection
