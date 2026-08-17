from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.pipeline import compile_source, run_source


def test_partial_field_move_can_be_reinitialized_before_use() -> None:
    source = (
        "record User:\n"
        "    name: text\n"
        "    count: tryte\n"
        "fn main() -> i64:\n"
        '    mut user: User = User(name=text_from_static("old"), count=3)\n'
        "    name: text = user.name\n"
        '    user.name = text_from_static("new")\n'
        "    return text_len(&user.name) + text_len(&name)\n"
    )

    assert run_source(source, optimization="O0") == 6
    assert run_source(source, optimization="O1") == 6


def test_partial_field_move_is_rejected_until_reinitialized() -> None:
    source = (
        "record User:\n"
        "    name: text\n"
        "fn main() -> i64:\n"
        '    user: User = User(name=text_from_static("old"))\n'
        "    name: text = user.name\n"
        "    return text_len(&user.name)\n"
    )

    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_USE_AFTER_MOVE


def test_all_match_paths_moving_an_owner_leave_it_moved_after_join() -> None:
    source = (
        "record User:\n"
        "    name: text\n"
        "fn consume(value: User) -> i64:\n"
        "    return text_len(&value.name)\n"
        "fn main() -> i64:\n"
        '    user: User = User(name=text_from_static("x"))\n'
        "    match 0:\n"
        "        -1:\n"
        "            discard consume(user)\n"
        "        0:\n"
        "            discard consume(user)\n"
        "        1:\n"
        "            discard consume(user)\n"
        "    return text_len(&user.name)\n"
    )

    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_USE_AFTER_MOVE


def test_mismatched_owned_states_at_join_are_rejected() -> None:
    source = (
        "record User:\n"
        "    name: text\n"
        "fn consume(value: User) -> i64:\n"
        "    return text_len(&value.name)\n"
        "fn main() -> i64:\n"
        '    user: User = User(name=text_from_static("x"))\n'
        "    match 0:\n"
        "        -1:\n"
        "            discard consume(user)\n"
        "        0:\n"
        "            discard 0\n"
        "        1:\n"
        "            discard 0\n"
        "    return 0\n"
    )

    with pytest.raises(SemanticError, match="control-flow join"):
        compile_source(source)


def test_loop_move_that_is_not_reinitialized_is_rejected_at_backedge() -> None:
    source = (
        "record User:\n"
        "    name: text\n"
        "fn main() -> i64:\n"
        '    user: User = User(name=text_from_static("x"))\n'
        "    while 0:\n"
        "        name: text = user.name\n"
        "    return 0\n"
    )

    with pytest.raises(SemanticError, match="control-flow join"):
        compile_source(source)


def test_whole_owner_assignment_reinitializes_a_moved_binding() -> None:
    source = (
        "record User:\n"
        "    name: text\n"
        "fn main() -> i64:\n"
        '    user: User = User(name=text_from_static("old"))\n'
        '    replacement: User = User(name=text_from_static("new"))\n'
        "    mut target: User = replacement\n"
        "    target = user\n"
        "    return text_len(&target.name)\n"
    )

    assert run_source(source, optimization="O0") == 3
    assert run_source(source, optimization="O1") == 3


def test_conditional_field_move_and_reinitialization_join_cleanly() -> None:
    source = (
        "record User:\n"
        "    name: text\n"
        "fn main() -> i64:\n"
        '    mut user: User = User(name=text_from_static("old"))\n'
        "    match 0:\n"
        "        -1:\n"
        "            name: text = user.name\n"
        '            user.name = text_from_static("branch")\n'
        "        0:\n"
        "            discard 0\n"
        "        1:\n"
        "            discard 0\n"
        "    return text_len(&user.name)\n"
    )

    assert run_source(source, optimization="O0") == 3
    assert run_source(source, optimization="O1") == 3


def test_array_element_field_move_and_reinitialization_is_path_sensitive() -> None:
    source = (
        "record User:\n"
        "    name: text\n"
        "fn main() -> i64:\n"
        '    mut users: User[1] = [User(name=text_from_static("old"))]\n'
        "    name: text = users[0].name\n"
        '    users[0].name = text_from_static("new")\n'
        "    return text_len(&users[0].name) + text_len(&name)\n"
    )

    assert run_source(source, optimization="O0") == 6
    assert run_source(source, optimization="O1") == 6
