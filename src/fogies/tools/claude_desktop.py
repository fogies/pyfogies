"""Tool reading which sessions the Claude desktop app lists.

The app keeps a record of each session it lists in its own data directory, which
is private to it and not documented, so this only reads, and reads defensively.
It is outside the Claude Code directory (`~/.claude`), so it is not carried by
tools that sync that (e.g., claude-sync), and its records name directories on
the machine they are on. A session is in the app's sidebar on a machine only if
the app has a record of it there, whatever transcripts are there.

Opening a session in the app, so that it has a record, is done by the Claude Code
CLI. See fogies.tools.claude_code.
"""

import os
import pathlib
import sys
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class DesktopSession(BaseModel):
    """What the app has recorded of a session, as it names it in its record.

    The app's records have more than is read here, and what it adds is not ours
    to refuse, so unlike our own configuration, extra fields are ignored.
    """

    # Read by the names in the app's records, or by these.
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, validate_by_name=True)

    session_id: str = Field(validation_alias="cliSessionId")
    # Hidden from the sidebar, as archived sessions are, but kept.
    archived: bool = Field(default=False, validation_alias="isArchived")
    title: str | None = None


def desktop_sessions_directory() -> pathlib.Path | None:
    """Return where the app records its sessions on this machine, or None if it can't be.

    If the app has no records here, this is where a regular install would keep them.
    """
    candidates: list[pathlib.Path] = []
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        if app_data:
            candidates.append(
                pathlib.Path(app_data) / "Claude" / "claude-code-sessions"
            )
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            # The Microsoft Store install keeps its data in a directory named for
            # its package, rather than in the roaming profile.
            candidates.extend(
                sorted(
                    (pathlib.Path(local_app_data) / "Claude-Data").glob(
                        "*/claude-code-sessions"
                    )
                )
            )
    elif sys.platform == "darwin":
        candidates.append(
            pathlib.Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude-code-sessions"
        )

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0] if candidates else None


def desktop_sessions(
    *, directory: pathlib.Path | None = None
) -> dict[str, DesktopSession] | None:
    """Return the sessions the app has recorded, by session ID.

    That is None if the app has no directory of records here (not installed, or
    not used), which is not the same as it having none. A record that can't be
    read is skipped, but if records exist and none can be read then the app's
    format is not what this reads, which raises ValueError rather than reporting
    that there are no sessions.
    """
    if directory is None:
        directory = desktop_sessions_directory()
    if directory is None or not directory.is_dir():
        return None

    sessions: dict[str, DesktopSession] = {}
    record_count = 0
    for path in directory.rglob("local_*.json"):
        record_count += 1
        try:
            session = DesktopSession.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except OSError, ValueError:
            # Not JSON, or not a session that can be resumed (e.g., one that is
            # new). ValueError is also what a record that does not validate raises.
            continue
        sessions[session.session_id] = session

    if record_count > 0 and not sessions:
        raise ValueError(
            "The format of the Claude desktop app's records in '{}' is not recognised.".format(
                directory
            )
        )
    return sessions
