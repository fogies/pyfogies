"""Tool for finding and describing Claude Code sessions.

Sessions are listed and deleted with the Claude Agent SDK, which tasks call
directly. See <https://code.claude.com/docs/en/agent-sdk/python>. This is what
is wanted on top of it: finding a session from part of its ID, and describing
one in a line.
"""

import datetime
import pathlib

from claude_agent_sdk import SDKSessionInfo

# Longest title shown in a line describing a session.
_TITLE_LENGTH = 60


def find_session_id(session_ids: list[str], value: str) -> str:
    """Return the session ID that value identifies, from any part of it.

    That includes the start of it, as with git, and all of it. Raises
    ValueError if no ID has the part, or if more than one does.
    """
    wanted = value.strip().lower()
    if not wanted:
        raise ValueError("Give at least part of a session's ID.")

    matches = [i for i in session_ids if wanted in i.lower()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ValueError(
            "'{}' matches {} sessions: {}. Give more of it.".format(
                value, len(matches), ", ".join(matches)
            )
        )
    raise ValueError("No session '{}'".format(value))


def describe_session(session: SDKSessionInfo) -> str:
    """Return a line describing a session: its ID, when it was modified, where it ran, and its title."""
    # The transcript's modified time. For a session synced from another
    # machine (e.g., by claude-sync), that is when it was synced.
    modified = (
        datetime.datetime.fromtimestamp(session.last_modified / 1000)
        .astimezone()
        .strftime("%Y-%m-%d %H:%M")
    )
    project = pathlib.Path(session.cwd).name if session.cwd is not None else "?"
    title = " ".join((session.summary or "").split())
    if len(title) > _TITLE_LENGTH:
        title = title[: _TITLE_LENGTH - 3] + "..."
    return "{}  {}  {:<24}  {}".format(session.session_id, modified, project, title)
