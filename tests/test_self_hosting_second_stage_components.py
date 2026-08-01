from __future__ import annotations

import os
from pathlib import Path

import pytest

from bootstrap.s3.assembly import AssemblyProgram
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    generate_native_assembly,
)
from bootstrap.s3.diagnostics import DiagnosticCategory, DiagnosticPhase
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import compile_sources


ROOT = Path(__file__).parents[1]
NATIVE_REQUIRED = os.environ.get("S3_NATIVE_REQUIRED") == "1"

DIAGNOSTIC_MODULE = "selfhost.diagnostics.diagnostic_classifier"
LAYOUT_MODULE = "selfhost.layout.discriminant_validator"


@pytest.fixture(scope="session")
def native_toolchain() -> NativeToolchain:
    try:
        return NativeToolchain.detect()
    except NativeBackendError as error:
        if NATIVE_REQUIRED:
            pytest.fail(f"required native toolchain unavailable: {error}")
        pytest.skip(str(error))


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _main_source(imports: str, expression: str, return_type: str = "tryte") -> str:
    return (
        "module main\n"
        f"{imports}"
        f"fn main() -> {return_type}:\n"
        f"    return {expression}\n"
    )


def _diagnostic_sources(main_source: str) -> dict[str, str]:
    return {
        "selfhost/diagnostics/diagnostic_classifier.s3": _source(
            "selfhost/diagnostics/diagnostic_classifier.s3"
        ),
        "main.s3": main_source,
    }


def _layout_sources(main_source: str) -> dict[str, str]:
    return {
        "selfhost/layout/discriminant_validator.s3": _source(
            "selfhost/layout/discriminant_validator.s3"
        ),
        "main.s3": main_source,
    }


def _assembly(sources: dict[str, str], optimization: str) -> AssemblyProgram:
    return compile_sources(sources, optimization).assembly


def _run(sources: dict[str, str], optimization: str) -> int:
    return Emulator().execute(_assembly(sources, optimization))


def _diagnostic_imports() -> str:
    return (
        f"from {DIAGNOSTIC_MODULE} import diagnostic_category_count\n"
        f"from {DIAGNOSTIC_MODULE} import diagnostic_phase_count\n"
        f"from {DIAGNOSTIC_MODULE} import diagnostic_category_is_known\n"
        f"from {DIAGNOSTIC_MODULE} import diagnostic_phase_is_known\n"
        f"from {DIAGNOSTIC_MODULE} import diagnostic_probe_is_known\n"
        f"from {DIAGNOSTIC_MODULE} import diagnostic_family_code_at\n"
        f"from {DIAGNOSTIC_MODULE} import diagnostic_channel_code_at\n"
        f"from {DIAGNOSTIC_MODULE} import diagnostic_classifier_smoke\n"
    )


def _layout_imports() -> str:
    return (
        f"from {LAYOUT_MODULE} import enum_tag_cell\n"
        f"from {LAYOUT_MODULE} import enum_max_variant_count\n"
        f"from {LAYOUT_MODULE} import enum_max_payload_width\n"
        f"from {LAYOUT_MODULE} import enum_variant_count_is_valid\n"
        f"from {LAYOUT_MODULE} import enum_discriminant_is_valid\n"
        f"from {LAYOUT_MODULE} import enum_payload_width_is_valid\n"
        f"from {LAYOUT_MODULE} import enum_total_width_for_payload\n"
        f"from {LAYOUT_MODULE} import enum_inactive_slot_count\n"
        f"from {LAYOUT_MODULE} import enum_layout_validator_smoke\n"
    )


def _reference_known(index: int, count: int) -> int:
    return -1 if 0 <= index < count else 0


def _reference_family_code(category_id: int) -> int:
    if _reference_known(category_id, len(tuple(DiagnosticCategory))) != -1:
        return -1
    if category_id <= 1:
        return 0
    if category_id <= 5:
        return 1
    if category_id <= 11:
        return 2
    return 3


def _reference_channel_code(phase_id: int) -> int:
    if _reference_known(phase_id, len(tuple(DiagnosticPhase))) != -1:
        return -1
    if phase_id <= 3:
        return 0
    if phase_id <= 7:
        return 1
    if phase_id <= 10:
        return 2
    return 3


def _reference_probe_known(category_id: int, phase_id: int) -> int:
    if _reference_known(category_id, len(tuple(DiagnosticCategory))) != -1:
        return 0
    if _reference_known(phase_id, len(tuple(DiagnosticPhase))) != -1:
        return 0
    return -1


def _reference_variant_count_valid(variant_count: int) -> int:
    return -1 if 1 <= variant_count <= 14 else 0


def _reference_discriminant_valid(discriminant: int, variant_count: int) -> int:
    if _reference_variant_count_valid(variant_count) != -1:
        return 0
    return -1 if 0 <= discriminant < variant_count else 0


def _reference_payload_width_valid(payload_width: int) -> int:
    return -1 if 0 <= payload_width <= 25 else 0


def _reference_total_width(payload_width: int) -> int:
    if _reference_payload_width_valid(payload_width) != -1:
        return -1
    return payload_width + 1


def _reference_inactive_slots(total_payload_width: int, variant_payload_width: int) -> int:
    if _reference_payload_width_valid(total_payload_width) != -1:
        return -1
    if _reference_payload_width_valid(variant_payload_width) != -1:
        return -1
    if variant_payload_width > total_payload_width:
        return -1
    return total_payload_width - variant_payload_width


def _run_diagnostic(expression: str, return_type: str = "tryte") -> tuple[int, int]:
    source = _main_source(_diagnostic_imports(), expression, return_type)
    sources = _diagnostic_sources(source)
    return (_run(sources, "O0"), _run(sources, "O1"))


def _run_layout(expression: str, return_type: str = "tryte") -> tuple[int, int]:
    source = _main_source(_layout_imports(), expression, return_type)
    sources = _layout_sources(source)
    return (_run(sources, "O0"), _run(sources, "O1"))


def test_diagnostic_classifier_inventory_matches_python_reference() -> None:
    assert _run_diagnostic("diagnostic_category_count()") == (
        len(tuple(DiagnosticCategory)),
        len(tuple(DiagnosticCategory)),
    )
    assert _run_diagnostic("diagnostic_phase_count()") == (
        len(tuple(DiagnosticPhase)),
        len(tuple(DiagnosticPhase)),
    )


@pytest.mark.parametrize("category_id", (-1, 0, 1, 2, 5, 6, 11, 12, 15, 16))
def test_diagnostic_family_matches_python_reference(category_id: int) -> None:
    expected_known = _reference_known(category_id, len(tuple(DiagnosticCategory)))
    expected_family = _reference_family_code(category_id)

    assert _run_diagnostic(f"diagnostic_category_is_known({category_id})", "trit") == (
        expected_known,
        expected_known,
    )
    assert _run_diagnostic(f"diagnostic_family_code_at({category_id})") == (
        expected_family,
        expected_family,
    )


@pytest.mark.parametrize("phase_id", (-1, 0, 3, 4, 7, 8, 10, 11, 14, 15))
def test_diagnostic_channel_matches_python_reference(phase_id: int) -> None:
    expected_known = _reference_known(phase_id, len(tuple(DiagnosticPhase)))
    expected_channel = _reference_channel_code(phase_id)

    assert _run_diagnostic(f"diagnostic_phase_is_known({phase_id})", "trit") == (
        expected_known,
        expected_known,
    )
    assert _run_diagnostic(f"diagnostic_channel_code_at(2, {phase_id})") == (
        expected_channel,
        expected_channel,
    )


@pytest.mark.parametrize(
    ("category_id", "phase_id"),
    ((0, 0), (2, 4), (15, 14), (-1, 0), (0, 15), (16, 15)),
)
def test_diagnostic_probe_known_matches_python_reference(
    category_id: int, phase_id: int
) -> None:
    expected = _reference_probe_known(category_id, phase_id)
    assert _run_diagnostic(
        f"diagnostic_probe_is_known({category_id}, {phase_id})",
        "trit",
    ) == (expected, expected)


def test_diagnostic_wrapper_exercises_payload_enum_bindings() -> None:
    source = (
        "module main\n"
        f"from {DIAGNOSTIC_MODULE} import diagnostic_family_code_at\n"
        "\n"
        "enum DiagnosticResult:\n"
        "    Known(value: tryte)\n"
        "    Invalid(value: tryte)\n"
        "\n"
        "fn main() -> tryte:\n"
        "    code: tryte = diagnostic_family_code_at(6)\n"
        "    result: DiagnosticResult = DiagnosticResult.Known(value=code)\n"
        "    match result:\n"
        "        DiagnosticResult.Known(value):\n"
        "            return value\n"
        "        DiagnosticResult.Invalid(value):\n"
        "            return -1\n"
    )
    sources = _diagnostic_sources(source)
    expected = _reference_family_code(6)
    assert _run(sources, "O0") == expected
    assert _run(sources, "O1") == expected


@pytest.mark.parametrize("variant_count", (-1, 0, 1, 2, 14, 15))
def test_discriminant_variant_count_matches_python_reference(variant_count: int) -> None:
    expected = _reference_variant_count_valid(variant_count)
    assert _run_layout(
        f"enum_variant_count_is_valid({variant_count})",
        "trit",
    ) == (expected, expected)


@pytest.mark.parametrize(
    ("discriminant", "variant_count"),
    ((0, 1), (1, 1), (2, 4), (4, 4), (-1, 4), (13, 14), (14, 14), (0, 15)),
)
def test_discriminant_validity_matches_python_reference(
    discriminant: int, variant_count: int
) -> None:
    expected = _reference_discriminant_valid(discriminant, variant_count)
    assert _run_layout(
        f"enum_discriminant_is_valid({discriminant}, {variant_count})",
        "trit",
    ) == (expected, expected)


@pytest.mark.parametrize("payload_width", (-1, 0, 1, 12, 25, 26))
def test_layout_width_matches_python_reference(payload_width: int) -> None:
    expected_valid = _reference_payload_width_valid(payload_width)
    expected_total = _reference_total_width(payload_width)

    assert _run_layout(
        f"enum_payload_width_is_valid({payload_width})",
        "trit",
    ) == (expected_valid, expected_valid)
    assert _run_layout(f"enum_total_width_for_payload({payload_width})") == (
        expected_total,
        expected_total,
    )


@pytest.mark.parametrize(
    ("total_payload_width", "variant_payload_width"),
    ((0, 0), (1, 0), (5, 2), (5, 5), (5, 6), (-1, 0), (26, 1)),
)
def test_inactive_slots_match_python_reference(
    total_payload_width: int, variant_payload_width: int
) -> None:
    expected = _reference_inactive_slots(total_payload_width, variant_payload_width)
    assert _run_layout(
        f"enum_inactive_slot_count({total_payload_width}, {variant_payload_width})"
    ) == (expected, expected)


def test_second_stage_components_compile_deterministically() -> None:
    diagnostic_sources = _diagnostic_sources(
        _main_source(_diagnostic_imports(), "diagnostic_classifier_smoke()")
    )
    layout_sources = _layout_sources(
        _main_source(_layout_imports(), "enum_layout_validator_smoke()")
    )

    assert _assembly(diagnostic_sources, "O1").render() == _assembly(
        dict(reversed(tuple(diagnostic_sources.items()))),
        "O1",
    ).render()
    assert _assembly(layout_sources, "O1").render() == _assembly(
        dict(reversed(tuple(layout_sources.items()))),
        "O1",
    ).render()


def test_native_second_stage_component_checksums_match_python_reference(
    native_toolchain: NativeToolchain,
    tmp_path: Path,
) -> None:
    diagnostic_expected = _reference_family_code(6) + _reference_channel_code(8)
    diagnostic_source = _main_source(
        _diagnostic_imports(),
        "diagnostic_family_code_at(6) + diagnostic_channel_code_at(6, 8)",
    )
    layout_expected = _reference_total_width(5) + _reference_inactive_slots(5, 2)
    layout_source = _main_source(
        _layout_imports(),
        "enum_total_width_for_payload(5) + enum_inactive_slot_count(5, 2)",
    )

    checks = (
        ("diagnostic", _diagnostic_sources(diagnostic_source), diagnostic_expected),
        ("layout", _layout_sources(layout_source), layout_expected),
    )
    for name, sources, expected in checks:
        for level in ("O0", "O1"):
            program = _assembly(sources, level)
            assert Emulator().execute(program) == expected
            executable = native_toolchain.build(
                generate_native_assembly(program),
                tmp_path / f"{name}-{level.lower()}",
            )
            completed = native_toolchain.run(executable)
            assert completed.returncode == 0
            assert completed.stderr == ""
            assert completed.stdout == f"program returned: {expected}\n"
