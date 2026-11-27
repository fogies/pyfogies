"""Test finding Claude Code sessions."""

import pytest

from fogies.tools.claude_sessions import find_session_id

# Two sessions that start the same, so that the start of their IDs is ambiguous.
_SAME_START_1 = "60c0de8b-271f-4239-830d-bbe9838a631c"
_SAME_START_2 = "60d1aa00-0000-4000-8000-000000000000"
# A session that is the only one to start differently.
_UNIQUE = "f542028f-01b1-4734-ad54-e30e6b957005"

_IDS = [_SAME_START_1, _SAME_START_2, _UNIQUE]


def test_find_session_id_from_part_of_it() -> None:
    """Any part of an ID, from any case, that is in only one, including all of it."""
    # The start, as with git.
    assert find_session_id(_IDS, "f54") == _UNIQUE
    assert find_session_id(_IDS, "F542028F") == _UNIQUE
    # From inside it.
    assert find_session_id(_IDS, "01b1") == _UNIQUE
    # All of it.
    assert find_session_id(_IDS, _UNIQUE) == _UNIQUE


@pytest.mark.parametrize(
    ("value", "match"),
    [
        ("60", "matches 2 sessions"),
        ("zzzz", "No session"),
        ("  ", "at least part"),
    ],
    ids=["ambiguous", "none", "empty"],
)
def test_find_session_id_that_is_not_one(value: str, match: str) -> None:
    """An empty value is in every ID, so it is refused rather than matching one."""
    with pytest.raises(ValueError, match=match):
        _ = find_session_id(_IDS, value)
