from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from bootstrap.s3.assembly import AssemblyOpcode, AssemblyProgram
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    generate_native_assembly,
)
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import compile_sources


ROOT = Path(__file__).parents[1]
CLASSIFIER_MODULE = "selfhost.assembly.opcode_classifier"
NATIVE_REQUIRED = os.environ.get("S3_NATIVE_REQUIRED") == "1"

OPCODES = (
    AssemblyOpcode.TCONST,
    AssemblyOpcode.TCONST_STR,
    AssemblyOpcode.TMOV,
    AssemblyOpcode.TINV,
    AssemblyOpcode.TADD,
    AssemblyOpcode.TMIN,
    AssemblyOpcode.TMAX,
    AssemblyOpcode.TCMP,
    AssemblyOpcode.TCALL,
    AssemblyOpcode.TLOAD,
    AssemblyOpcode.TSTORE,
    AssemblyOpcode.TRET,
    AssemblyOpcode.TJMP,
    AssemblyOpcode.TBR3,
)

KIND_CODES = {
    AssemblyOpcode.TCONST: 0,
    AssemblyOpcode.TCONST_STR: 0,
    AssemblyOpcode.TMOV: 0,
    AssemblyOpcode.TINV: 0,
    AssemblyOpcode.TADD: 0,
    AssemblyOpcode.TMIN: 0,
    AssemblyOpcode.TMAX: 0,
    AssemblyOpcode.TCMP: 0,
    AssemblyOpcode.TCALL: 0,
    AssemblyOpcode.TLOAD: 1,
    AssemblyOpcode.TSTORE: 1,
    AssemblyOpcode.TRET: 2,
    AssemblyOpcode.TJMP: 2,
    AssemblyOpcode.TBR3: 2,
}

MIN_OPERAND_COUNTS = {
    AssemblyOpcode.TCONST: 2,
    AssemblyOpcode.TCONST_STR: 2,
    AssemblyOpcode.TMOV: 2,
    AssemblyOpcode.TINV: 2,
    AssemblyOpcode.TADD: 3,
    AssemblyOpcode.TMIN: 3,
    AssemblyOpcode.TMAX: 3,
    AssemblyOpcode.TCMP: 3,
    AssemblyOpcode.TCALL: 2,
    AssemblyOpcode.TLOAD: 3,
    AssemblyOpcode.TSTORE: 3,
    AssemblyOpcode.TRET: 1,
    AssemblyOpcode.TJMP: 1,
    AssemblyOpcode.TBR3: 4,
}

VARIADIC = {AssemblyOpcode.TCALL}


@pytest.fixture(scope="session")
def native_toolchain() -> NativeToolchain:
    try:
        return NativeToolchain.detect()
    except NativeBackendError as error:
        if NATIVE_REQUIRED:
            pytest.fail(f"required native toolchain unavailable: {error}")
        pytest.skip(str(error))


def _component_sources(main_source: str) -> dict[str, str]:
    return {
        "selfhost/assembly/opcode_ids.s3": (
            ROOT / "selfhost/assembly/opcode_ids.s3"
        ).read_text(encoding="utf-8"),
        "selfhost/assembly/opcode_classifier.s3": (
            ROOT / "selfhost/assembly/opcode_classifier.s3"
        ).read_text(encoding="utf-8"),
        "main.s3": main_source,
    }


def _main_source(expression: str, return_type: str = "tryte") -> str:
    return (
        "module main\n"
        f"from {CLASSIFIER_MODULE} import opcode_is_known_id\n"
        f"from {CLASSIFIER_MODULE} import opcode_kind_code_at\n"
        f"from {CLASSIFIER_MODULE} import opcode_min_operand_count_at\n"
        f"from {CLASSIFIER_MODULE} import opcode_is_variadic_at\n"
        f"from {CLASSIFIER_MODULE} import opcode_accepts_operand_count_id\n"
        f"from {CLASSIFIER_MODULE} import opcode_classifier_smoke\n"
        f"fn main() -> {return_type}:\n"
        f"    return {expression}\n"
    )


def _assembly_for(expression: str, return_type: str = "tryte", optimization: str = "O0") -> AssemblyProgram:
    return compile_sources(
        _component_sources(_main_source(expression, return_type)),
        optimization,
    ).assembly


def _run_s3(expression: str, return_type: str = "tryte", optimization: str = "O0") -> int:
    return Emulator().execute(_assembly_for(expression, return_type, optimization))


def _opcode_id(opcode: AssemblyOpcode) -> int:
    return OPCODES.index(opcode)


def _reference_is_known_id(opcode_id: int) -> int:
    return -1 if 0 <= opcode_id < len(OPCODES) else 0


def _reference_kind_code_at(opcode_id: int) -> int:
    if _reference_is_known_id(opcode_id) != -1:
        return -1
    return KIND_CODES[OPCODES[opcode_id]]


def _reference_min_operand_count_at(opcode_id: int) -> int:
    if _reference_is_known_id(opcode_id) != -1:
        return -1
    return MIN_OPERAND_COUNTS[OPCODES[opcode_id]]


def _reference_is_variadic_at(opcode_id: int) -> int:
    if _reference_is_known_id(opcode_id) != -1:
        return 0
    return -1 if OPCODES[opcode_id] in VARIADIC else 0


def _reference_accepts_operand_count_id(opcode_id: int, count: int) -> int:
    if _reference_is_known_id(opcode_id) != -1:
        return 0
    opcode = OPCODES[opcode_id]
    minimum = MIN_OPERAND_COUNTS[opcode]
    if count == minimum:
        return -1
    if opcode in VARIADIC and count > minimum:
        return -1
    return 0


def _checksum_tryte_expression() -> str:
    return (
        "opcode_classifier_smoke()"
        " + opcode_kind_code_at(9)"
        " + opcode_kind_code_at(13)"
        " + opcode_min_operand_count_at(0)"
        " + opcode_min_operand_count_at(8)"
        " + opcode_min_operand_count_at(13)"
        " + opcode_kind_code_at(-1)"
        " + opcode_min_operand_count_at(14)"
    )


def _reference_checksum_tryte() -> int:
    return (
        len(OPCODES)
        + _reference_kind_code_at(9)
        + _reference_kind_code_at(13)
        + _reference_min_operand_count_at(0)
        + _reference_min_operand_count_at(8)
        + _reference_min_operand_count_at(13)
        + _reference_kind_code_at(-1)
        + _reference_min_operand_count_at(14)
    )


def test_python_reference_covers_current_assembly_opcode_inventory() -> None:
    assert set(OPCODES) <= set(AssemblyOpcode)
    assert set(KIND_CODES) == set(OPCODES)
    assert set(MIN_OPERAND_COUNTS) == set(OPCODES)
    assert VARIADIC == {AssemblyOpcode.TCALL}


@pytest.mark.parametrize("opcode", OPCODES)
def test_s3_opcode_classifier_matches_python_reference_for_all_opcodes(
    opcode: AssemblyOpcode,
) -> None:
    opcode_id = _opcode_id(opcode)
    expectations = (
        (
            f"opcode_is_known_id({opcode_id})",
            "trit",
            _reference_is_known_id(opcode_id),
        ),
        (
            f"opcode_kind_code_at({opcode_id})",
            "tryte",
            _reference_kind_code_at(opcode_id),
        ),
        (
            f"opcode_min_operand_count_at({opcode_id})",
            "tryte",
            _reference_min_operand_count_at(opcode_id),
        ),
        (
            f"opcode_is_variadic_at({opcode_id})",
            "trit",
            _reference_is_variadic_at(opcode_id),
        ),
    )

    for expression, return_type, expected in expectations:
        assert _run_s3(expression, return_type, "O0") == expected
        assert _run_s3(expression, return_type, "O1") == expected


@pytest.mark.parametrize(
    ("opcode_id", "count"),
    (
        (0, 2),
        (0, 1),
        (8, 2),
        (8, 5),
        (8, 1),
        (13, 4),
        (13, 5),
        (-1, 2),
        (14, 2),
    ),
)
def test_s3_opcode_operand_count_acceptance_matches_python_reference(
    opcode_id: int,
    count: int,
) -> None:
    expression = f"opcode_accepts_operand_count_id({opcode_id}, {count})"
    expected = _reference_accepts_operand_count_id(opcode_id, count)

    assert _run_s3(expression, "trit", "O0") == expected
    assert _run_s3(expression, "trit", "O1") == expected


def test_s3_opcode_classifier_handles_invalid_ids_like_python_reference() -> None:
    for opcode_id in (-1, 14):
        assert _run_s3(f"opcode_is_known_id({opcode_id})", "trit") == 0
        assert _run_s3(f"opcode_kind_code_at({opcode_id})") == -1
        assert _run_s3(f"opcode_min_operand_count_at({opcode_id})") == -1
        assert _run_s3(f"opcode_is_variadic_at({opcode_id})", "trit") == 0


def test_s3_opcode_classifier_compilation_is_deterministic() -> None:
    sources = _component_sources(_main_source("opcode_classifier_smoke()"))
    forward = compile_sources(tuple(sources.items()), "O1").assembly.render()
    backward = compile_sources(tuple(reversed(tuple(sources.items()))), "O1").assembly.render()

    assert forward == backward


def test_opcode_classifier_checksum_matches_python_reference() -> None:
    tryte_expression = _checksum_tryte_expression()
    tryte_expected = _reference_checksum_tryte()
    trit_expression = "opcode_is_variadic_at(8)"
    trit_expected = _reference_is_variadic_at(8)

    for level in ("O0", "O1"):
        assert _run_s3(tryte_expression, "tryte", level) == tryte_expected
        assert _run_s3(trit_expression, "trit", level) == trit_expected


def test_native_opcode_classifier_checksum_matches_python_reference(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    tryte_expression = _checksum_tryte_expression()
    tryte_expected = _reference_checksum_tryte()
    trit_expression = "opcode_is_variadic_at(8)"
    trit_expected = _reference_is_variadic_at(8)

    for level in ("O0", "O1"):
        program = _assembly_for(tryte_expression, "tryte", level)
        assert Emulator().execute(program) == tryte_expected
        executable = native_toolchain.build(
            generate_native_assembly(program),
            tmp_path / f"{level.lower()}-tryte",
        )
        completed = native_toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stderr == ""
        assert completed.stdout == f"program returned: {tryte_expected}\n"

        trit_program = _assembly_for(trit_expression, "trit", level)
        assert Emulator().execute(trit_program) == trit_expected
        trit_executable = native_toolchain.build(
            generate_native_assembly(trit_program),
            tmp_path / f"{level.lower()}-trit",
        )
        trit_completed = native_toolchain.run(trit_executable)
        assert trit_completed.returncode == 0
        assert trit_completed.stderr == ""
        assert trit_completed.stdout == f"program returned: {trit_expected}\n"
