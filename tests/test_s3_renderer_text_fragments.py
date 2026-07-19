from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import CompilationResult, compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


TEXT_FRAGMENT_PATH = Path(
    "examples/self_hosting/assembly_renderer_text_fragments.s3"
)
GOLDEN_PATHS = {
    "first": Path("tests/golden/inspect/first.assembly.txt"),
    "simple_call": Path("tests/golden/inspect/simple_call.assembly.txt"),
    "sign": Path("tests/golden/inspect/sign.assembly.txt"),
}


def _source() -> str:
    return TEXT_FRAGMENT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def compilation() -> CompilationResult:
    return compile_source(_source())


def _execute(compilation: CompilationResult, entry: str) -> int:
    return Emulator(max_instructions=1_000_000).execute(
        compilation.assembly,
        entry=entry,
    )


def _fragment_metrics(path: Path) -> dict[str, int]:
    fragments: list[tuple[str, int]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            fragments.append(("blank", 1))
            continue
        if line.startswith(".s3asm "):
            fragments.extend(
                (
                    ("document_marker", 6),
                    ("space", 1),
                    ("immediate", len(line[7:])),
                    ("newline", 1),
                )
            )
            continue
        if line == ".end":
            fragments.extend((("document_end", 4), ("newline", 1)))
            continue
        if line.startswith(".function "):
            match = re.fullmatch(r"(.function) (.+) -> (.+)", line)
            assert match is not None
            fragments.extend(
                (
                    ("directive", len(match.group(1))),
                    ("space", 1),
                    ("symbol", len(match.group(2))),
                    ("space", 1),
                    ("separator", 2),
                    ("space", 1),
                    ("type", len(match.group(3))),
                    ("newline", 1),
                )
            )
            continue
        if line.startswith(".label "):
            fragments.extend(
                (("directive", 6), ("space", 1), ("symbol", len(line[7:])), ("newline", 1))
            )
            continue
        if line.startswith("    ."):
            match = re.fullmatch(r"    (\.[a-z]+) (r\d+), ([a-z]+)", line)
            assert match is not None
            fragments.extend(
                (
                    ("indentation", 4),
                    ("directive", len(match.group(1))),
                    ("space", 1),
                    ("register", len(match.group(2))),
                    ("separator", 1),
                    ("space", 1),
                    ("type", len(match.group(3))),
                    ("newline", 1),
                )
            )
            continue

        match = re.fullmatch(r"    ([A-Z0-9]+) +(.*?) ; source=(.+)", line)
        assert match is not None
        _, operands, source = match.groups()
        fragments.extend((("indentation", 4), ("opcode", 6), ("space", 1)))
        for index, operand in enumerate(operands.split(", ")):
            if index:
                fragments.extend((("separator", 1), ("space", 1)))
            category = (
                "register"
                if re.fullmatch(r"r\d+", operand)
                else "immediate"
                if re.fullmatch(r"-?\d+", operand)
                else "symbol"
            )
            fragments.append((category, len(operand)))
        fragments.extend(
            (("source_prefix", 10), ("source_value", len(source)), ("newline", 1))
        )

    categories = Counter(category for category, _ in fragments)
    token_categories = {
        "document_marker",
        "directive",
        "opcode",
        "symbol",
        "type",
        "register",
        "immediate",
        "document_end",
    }
    logical_bytes = len(
        path.read_bytes().decode("utf-8").replace("\r\n", "\n").encode("utf-8")
    )
    return {
        "fragments": len(fragments),
        "tokens": sum(categories[category] for category in token_categories),
        "indentation": categories["indentation"],
        "separators": categories["separator"],
        "metadata": categories["source_prefix"] + categories["source_value"],
        "newlines": categories["newline"] + categories["blank"],
        "blank": categories["blank"],
        "spaces": categories["space"],
        "lines": len(path.read_text(encoding="utf-8").splitlines()),
        "bytes": logical_bytes,
    }


def _compile_metric_probes() -> CompilationResult:
    probes: list[str] = []
    for fixture in ("first", "simple_call", "sign"):
        for metric in (
            "fragment_count",
            "fragment_token_count",
            "fragment_separator_count",
            "fragment_line_count",
        ):
            probes.append(
                f"fn probe_{fixture}_{metric}() -> tryte:\n"
                f"    return {fixture}_{metric}()\n"
            )
        probes.extend(
            (
                f"fn probe_{fixture}_metadata() -> tryte:\n"
                f"    return expected_metadata_fragment_count(fixture_{fixture}())\n",
                f"fn probe_{fixture}_indentation() -> tryte:\n"
                f"    return expected_indentation_fragment_count(fixture_{fixture}())\n",
                f"fn probe_{fixture}_blank() -> tryte:\n"
                f"    return expected_blank_fragment_count(fixture_{fixture}())\n",
                f"fn probe_{fixture}_spaces() -> tryte:\n"
                f"    return expected_space_fragment_count(fixture_{fixture}())\n",
                f"fn probe_{fixture}_newline() -> tryte:\n"
                f"    return expected_newline_fragment_count(fixture_{fixture}())\n",
            )
        )
    return compile_source(_source() + "\n" + "\n".join(probes))


def test_renderer_text_fragment_model_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert TEXT_FRAGMENT_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source


def test_renderer_text_fragment_model_compiles_and_executes_hosted(
    compilation: CompilationResult,
) -> None:
    names = {function.name for function in compilation.ast.functions}

    assert {
        "main",
        "text_fragment_model_self_check",
        "expected_fragment_at",
        "fragment_logical_byte_count",
        "next_fragment_state",
        "is_valid_byte_pair",
        "validate_fixture_fragment_sequence",
        "validate_fixture_fragment_counts",
        "validate_fixture_fragment_bytes",
        "validate_fixture_fragment_signature",
        "validate_builder_fragment_consistency",
        "validate_total_fragment_signature",
    } <= names
    assert run_source(_source()) == 0
    assert run_source(_source(), entry="text_fragment_model_self_check") == 0
    assert _execute(compilation, "validate_all_fixture_fragments") == 1


def test_fragment_metrics_are_derived_from_the_real_goldens() -> None:
    expected = {name: _fragment_metrics(path) for name, path in GOLDEN_PATHS.items()}

    assert expected == {
        "first": {
            "fragments": 137,
            "tokens": 47,
            "indentation": 13,
            "separators": 14,
            "metadata": 14,
            "newlines": 18,
            "blank": 1,
            "spaces": 31,
            "lines": 18,
            "bytes": 441,
        },
        "simple_call": {
            "fragments": 145,
            "tokens": 51,
            "indentation": 12,
            "separators": 15,
            "metadata": 12,
            "newlines": 21,
            "blank": 2,
            "spaces": 34,
            "lines": 21,
            "bytes": 448,
        },
        "sign": {
            "fragments": 266,
            "tokens": 92,
            "indentation": 24,
            "separators": 26,
            "metadata": 28,
            "newlines": 36,
            "blank": 2,
            "spaces": 60,
            "lines": 36,
            "bytes": 946,
        },
    }

    probe_compilation = _compile_metric_probes()
    for fixture, metrics in expected.items():
        assert _execute(probe_compilation, f"probe_{fixture}_fragment_count") == metrics["fragments"]
        assert _execute(probe_compilation, f"probe_{fixture}_fragment_token_count") == metrics["tokens"]
        assert _execute(probe_compilation, f"probe_{fixture}_fragment_separator_count") == metrics["separators"]
        assert _execute(probe_compilation, f"probe_{fixture}_indentation") == metrics["indentation"]
        assert _execute(probe_compilation, f"probe_{fixture}_metadata") == metrics["metadata"]
        assert _execute(probe_compilation, f"probe_{fixture}_newline") == metrics["newlines"]
        assert _execute(probe_compilation, f"probe_{fixture}_blank") == metrics["blank"]
        assert _execute(probe_compilation, f"probe_{fixture}_spaces") == metrics["spaces"]
        assert _execute(probe_compilation, f"probe_{fixture}_fragment_line_count") == metrics["lines"]


def test_each_fixture_validates_its_fragment_sequence_and_builder_consistency(
    compilation: CompilationResult,
) -> None:
    for entry in (
        "validate_first_fragments",
        "validate_simple_call_fragments",
        "validate_sign_fragments",
    ):
        assert _execute(compilation, entry) == 1

    probe_source = _source() + """
fn probe_first_builder_consistency() -> tryte:
    return status_from_check(validate_builder_fragment_consistency(fixture_first()), 1)

fn probe_simple_builder_consistency() -> tryte:
    return status_from_check(validate_builder_fragment_consistency(fixture_simple_call()), 1)

fn probe_sign_builder_consistency() -> tryte:
    return status_from_check(validate_builder_fragment_consistency(fixture_sign()), 1)
"""
    probe_compilation = compile_source(probe_source)
    for entry in (
        "probe_first_builder_consistency",
        "probe_simple_builder_consistency",
        "probe_sign_builder_consistency",
    ):
        assert _execute(probe_compilation, entry) == 0


def test_byte_pairs_represent_all_fixture_byte_counts_without_overflow(
    compilation: CompilationResult,
) -> None:
    expected_pairs = {
        "first": (1, 141, 1, 96),
        "simple_call": (1, 148, 1, 96),
        "sign": (3, 46, 2, 165),
    }
    for fixture, (high, low, base_high, base_low) in expected_pairs.items():
        assert _execute(compilation, f"{fixture}_fragment_byte_count_high") == high
        assert _execute(compilation, f"{fixture}_fragment_byte_count_low") == low
        assert _execute(compilation, f"{fixture}_accumulated_base_byte_count_high") == base_high
        assert _execute(compilation, f"{fixture}_accumulated_base_byte_count_low") == base_low
        assert high * 300 + low == _fragment_metrics(GOLDEN_PATHS[fixture])["bytes"]

    assert _execute(compilation, "validate_invalid_byte_pair_probe") == 1
    assert _execute(compilation, "validate_invalid_byte_carry_probe") == 1
    assert _execute(compilation, "validate_byte_count_mismatch_probe") == 1


def test_fragment_ids_states_indexes_and_transitions_reject_invalid_values(
    compilation: CompilationResult,
) -> None:
    for entry in (
        "validate_invalid_fixture_probe",
        "validate_invalid_fragment_probe",
        "validate_invalid_state_probe",
        "validate_invalid_index_probe",
        "validate_invalid_transition_probe",
    ):
        assert _execute(compilation, entry) == 1


def test_fragment_signatures_and_line_consistency_are_deterministic(
    compilation: CompilationResult,
) -> None:
    assert _execute(compilation, "first_fragment_signature") == 75
    assert _execute(compilation, "simple_call_fragment_signature") == 78
    assert _execute(compilation, "sign_fragment_signature") == 146
    assert _execute(compilation, "validate_total_fragment_signature") == 1

    probe_source = _source() + """
fn probe_first_line_consistency() -> tryte:
    return status_from_check(validate_fragment_line_consistency(fixture_first()), 1)

fn probe_simple_line_consistency() -> tryte:
    return status_from_check(validate_fragment_line_consistency(fixture_simple_call()), 1)

fn probe_sign_line_consistency() -> tryte:
    return status_from_check(validate_fragment_line_consistency(fixture_sign()), 1)
"""
    probe_compilation = compile_source(probe_source)
    for entry in (
        "probe_first_line_consistency",
        "probe_simple_line_consistency",
        "probe_sign_line_consistency",
    ):
        assert _execute(probe_compilation, entry) == 0


def test_fragment_model_is_registered_without_renderer_output_contract_changes() -> None:
    program = find_program(TEXT_FRAGMENT_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0
