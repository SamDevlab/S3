from __future__ import annotations

import platform
from pathlib import Path

import pytest

from bootstrap.s3 import run_source
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    generate_native_assembly,
)
from bootstrap.s3.pipeline import compile_source


def _candidate_source(case_id: int) -> str:
    repository = Path(__file__).parents[1]
    lexer = (repository / "selfhost/substrate/generic_lexer_state.s3").read_text(
        encoding="utf-8"
    )
    semantic = (
        repository / "selfhost/substrate/native_semantic_execution.s3"
    ).read_text(encoding="utf-8")
    typed = (
        repository / "selfhost/substrate/native_typed_value_protocol.s3"
    ).read_text(encoding="utf-8")
    return (
        lexer
        + "\n"
        + semantic
        + "\n"
        + typed
        + f"\nfn main() -> i64:\n    return native_semantic_case({case_id})\n"
    )


def _candidate_literal_source(value: int) -> str:
    repository = Path(__file__).parents[1]
    lexer = (repository / "selfhost/substrate/generic_lexer_state.s3").read_text(
        encoding="utf-8"
    )
    semantic = (
        repository / "selfhost/substrate/native_semantic_execution.s3"
    ).read_text(encoding="utf-8")
    typed = (
        repository / "selfhost/substrate/native_typed_value_protocol.s3"
    ).read_text(encoding="utf-8")
    return (
        lexer
        + "\n"
        + semantic
        + "\n"
        + typed
        + f"\nfn main() -> i64:\n    return native_semantic_literal({value})\n"
    )


def _candidate_while_source(initial: int, limit: int) -> str:
    repository = Path(__file__).parents[1]
    lexer = (repository / "selfhost/substrate/generic_lexer_state.s3").read_text(
        encoding="utf-8"
    )
    semantic = (
        repository / "selfhost/substrate/native_semantic_execution.s3"
    ).read_text(encoding="utf-8")
    typed = (
        repository / "selfhost/substrate/native_typed_value_protocol.s3"
    ).read_text(encoding="utf-8")
    return (
        lexer
        + "\n"
        + semantic
        + "\n"
        + typed
        + f"\nfn main() -> i64:\n    return native_semantic_while({initial}, {limit})\n"
    )


def _candidate_f64_source() -> str:
    repository = Path(__file__).parents[1]
    lexer = (repository / "selfhost/substrate/generic_lexer_state.s3").read_text(
        encoding="utf-8"
    )
    semantic = (
        repository / "selfhost/substrate/native_semantic_execution.s3"
    ).read_text(encoding="utf-8")
    typed = (
        repository / "selfhost/substrate/native_typed_value_protocol.s3"
    ).read_text(encoding="utf-8")
    return (
        lexer
        + "\n"
        + semantic
        + "\n"
        + typed
        + "\nfn main() -> trit:\n    return native_typed_f64_case()\n"
    )


def _candidate_mixed_binary_source() -> str:
    repository = Path(__file__).parents[1]
    lexer = (repository / "selfhost/substrate/generic_lexer_state.s3").read_text(
        encoding="utf-8"
    )
    semantic = (
        repository / "selfhost/substrate/native_semantic_execution.s3"
    ).read_text(encoding="utf-8")
    typed = (
        repository / "selfhost/substrate/native_typed_value_protocol.s3"
    ).read_text(encoding="utf-8")
    return (
        lexer
        + "\n"
        + semantic
        + "\n"
        + typed
        + "\nfn main() -> trit:\n    return native_typed_mixed_binary_case()\n"
    )


def test_native_i64_semantic_literals_bindings_and_arithmetic() -> None:
    assert run_source(_candidate_source(0)) == 42


@pytest.mark.parametrize("value", (0, 1, 7, 17, 100, 999))
def test_native_i64_semantic_literal_is_not_42_specific(value: int) -> None:
    assert run_source(_candidate_literal_source(value)) == value


@pytest.mark.parametrize(
    ("initial", "limit", "expected"),
    ((0, 0, 0), (0, 1, 1), (0, 6, 6), (40, 42, 42)),
)
def test_native_i64_semantic_while_executes_zero_one_and_many_iterations(
    initial: int,
    limit: int,
    expected: int,
) -> None:
    assert run_source(_candidate_while_source(initial, limit)) == expected


def test_native_i64_semantic_calls_use_native_frames_and_arguments() -> None:
    assert run_source(_candidate_source(1)) == 42


def test_native_i64_semantic_while_updates_state_and_returns_after_loop() -> None:
    assert run_source(_candidate_source(2)) == 42


def test_native_i64_semantic_assignment_updates_local_state() -> None:
    assert run_source(_candidate_source(3)) == 42


def test_native_i64_semantic_grouping_preserves_expression_value() -> None:
    assert run_source(_candidate_source(4)) == 42


def test_native_typed_value_protocol_executes_f64_literal_call_and_return() -> None:
    assert run_source(_candidate_f64_source()) == -1


def test_native_typed_value_protocol_rejects_mixed_binary_types() -> None:
    assert run_source(_candidate_mixed_binary_source()) == -1


def test_native_typed_value_protocol_is_explicit_and_i64_wrappers_migrated() -> None:
    repository = Path(__file__).parents[1]
    protocol = (
        repository / "selfhost/substrate/native_typed_value_protocol.s3"
    ).read_text(encoding="utf-8")
    semantic = (
        repository / "selfhost/substrate/native_semantic_execution.s3"
    ).read_text(encoding="utf-8")
    assert "record NativeTypedValue:" in protocol
    assert "kind: i64" in protocol
    assert "i64_value: i64" in protocol
    assert "f64_value: f64" in protocol
    assert "record NativeTypedResult:" in protocol
    assert "status: i64" in protocol
    assert "native_typed_execute_i64_source(&source)" in semantic


def test_native_semantic_path_has_no_hosted_frontend_fallback() -> None:
    source = _candidate_source(2)
    for forbidden in (
        "GenericLexer(",
        "GenericParser(",
        "tokenize(",
        "parse_tokens(",
        "bootstrap.s3.ast",
        "run_source(",
    ):
        assert forbidden not in source


@pytest.mark.s3_native
def test_native_semantic_i64_program_qualifies_on_linux_x86_64(tmp_path: Path) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        pytest.skip("native semantic qualification requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))

    compilation = compile_source(_candidate_source(0))
    executable = toolchain.build(
        generate_native_assembly(compilation.assembly),
        tmp_path / "native-semantic-i64",
    )
    completed = toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stdout == "program returned: 42\n"
    assert completed.stderr == ""
