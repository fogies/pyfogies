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
    desktop_statuses,
    plan_resume,
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

        sessions = {session.session_id: session for session in list_sessions()}
        statuses = desktop_statuses(transcripts=sessions, recorded=recorded)
        for session_id, status in statuses.items():
            if session_id in sessions:
                print(
                    "{:<10}  {}".format(status, describe_session(sessions[session_id]))
                )
            else:
                print(
                    "{:<10}  {}  {}".format(
                        status, session_id, recorded[session_id].title or ""
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
            directories = {i: session.cwd for i, session in sessions.items()}
            # Archived sessions are recorded, so are not resumed.
            listed = recorded.keys()
        else:
            assert session_id is not None
            resume_id = find_session_id(list(sessions), session_id)
            directories = {resume_id: sessions[resume_id].cwd}
            listed = ()
        resumable, skipped = plan_resume(directories=directories, listed=listed)

        # One session that is asked for is an error. Skipping a session is for
        # when all of them are.
        if skipped and not all_:
            ((skipped_id, problem),) = skipped.items()
            raise ValueError("Session '{}' {}".format(skipped_id, problem))
        for skipped_id, problem in skipped.items():
            print("Skipping {}, as it {}.".format(skipped_id, problem))

        with claude_code(binary_cache_path=binary_cache_path) as cc:
            for resume_id, cwd in resumable.items():
                print("Resuming {}.".format(resume_id))
                cc.resume_in_desktop(session_id=resume_id, cwd=cwd)

        if all_:
            print(
                "Resumed {} of {} sessions not listed.".format(
                    len(resumable), len(resumable) + len(skipped)
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
