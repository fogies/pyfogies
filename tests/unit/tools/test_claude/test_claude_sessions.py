"""Test finding and describing Claude Code sessions."""

import pytest
from claude_agent_sdk import SDKSessionInfo

from fogies.tools.claude_sessions import describe_session, find_session_id

_IDS = [
    "60c0de8b-271f-4239-830d-bbe9838a631c",
    "60d1aa00-0000-4000-8000-000000000000",
    "f542028f-01b1-4734-ad54-e30e6b957005",
]


def test_find_session_id_from_part_of_it() -> None:
    """Any part of an ID, from any case, that is in only one, including all of it."""
    # The start, as with git.
    assert find_session_id(_IDS, "f54") == _IDS[2]
    assert find_session_id(_IDS, "F542028F") == _IDS[2]
    # From inside it.
    assert find_session_id(_IDS, "01b1") == _IDS[2]
    # All of it.
    assert find_session_id(_IDS, _IDS[2]) == _IDS[2]


@pytest.mark.parametrize(
    ("value", "match"),
    [
        ("60", "matches 2 sessions"),
        ("-", "matches 3 sessions"),
        ("zzzz", "No session"),
        ("  ", "at least part"),
    ],
    ids=["ambiguous start", "ambiguous inside", "none", "empty"],
)
def test_find_session_id_that_is_not_one(value: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _ = find_session_id(_IDS, value)


def test_describe_session() -> None:
    """A session is described by its ID, where it ran, and a title that is kept short."""
    session = SDKSessionInfo(
        session_id=_IDS[0],
        summary="Fix\nthe   thing " + "x" * 100,
        last_modified=1_700_000_000_000,
        cwd="/work/demo",
    )
    line = describe_session(session)
    assert line.startswith(_IDS[0])
    assert "demo" in line
    assert line.endswith("...")
    assert "\n" not in line
