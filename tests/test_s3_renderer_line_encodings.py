from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import CompilationResult, compile_source, run_source
from tools.s3_program_check import find_program, run_hosted_check


LINE_ENCODINGS_PATH = Path(
    "examples/self_hosting/assembly_renderer_line_encodings.s3"
)
GOLDEN_PATHS = {
    "first": Path("tests/golden/inspect/first.assembly.txt"),
    "simple_call": Path("tests/golden/inspect/simple_call.assembly.txt"),
    "sign": Path("tests/golden/inspect/sign.assembly.txt"),
}
ACTUAL_OUTPUT_PATHS = {
    "first": Path("tests/golden/assembly_renderer_candidate_actual/first.assembly.txt"),
    "simple_call": Path(
        "tests/golden/assembly_renderer_candidate_actual/simple_call.assembly.txt"
    ),
    "sign": Path("tests/golden/assembly_renderer_candidate_actual/sign.assembly.txt"),
}
METRIC_ENTRYPOINTS = {
    "line_count": {
        "first": "first_line_count",
        "simple_call": "simple_call_line_count",
        "sign": "sign_line_count",
    },
    "encoded_line_count": {
        "first": "first_encoded_line_count",
        "simple_call": "simple_call_encoded_line_count",
        "sign": "sign_encoded_line_count",
    },
    "instruction_count": {
        "first": "first_instruction_encoding_count",
        "simple_call": "simple_call_instruction_encoding_count",
        "sign": "sign_instruction_encoding_count",
    },
    "directive_count": {
        "first": "first_directive_encoding_count",
        "simple_call": "simple_call_directive_encoding_count",
        "sign": "sign_directive_encoding_count",
    },
    "blank_count": {
        "first": "first_blank_encoding_count",
        "simple_call": "simple_call_blank_encoding_count",
        "sign": "sign_blank_encoding_count",
    },
    "opcode_count": {
        "first": "first_opcode_encoding_count",
        "simple_call": "simple_call_opcode_encoding_count",
        "sign": "sign_opcode_encoding_count",
    },
    "register_operand_line_count": {
        "first": "first_register_operand_line_count",
        "simple_call": "simple_call_register_operand_line_count",
        "sign": "sign_register_operand_line_count",
    },
    "immediate_line_count": {
        "first": "first_immediate_line_count",
        "simple_call": "simple_call_immediate_line_count",
        "sign": "sign_immediate_line_count",
    },
    "callee_line_count": {
        "first": "first_callee_line_count",
        "simple_call": "simple_call_callee_line_count",
        "sign": "sign_callee_line_count",
    },
    "label_operand_line_count": {
        "first": "first_label_operand_line_count",
        "simple_call": "simple_call_label_operand_line_count",
        "sign": "sign_label_operand_line_count",
    },
    "memory_operand_line_count": {
        "first": "first_memory_operand_line_count",
        "simple_call": "simple_call_memory_operand_line_count",
        "sign": "sign_memory_operand_line_count",
    },
    "source_metadata_line_count": {
        "first": "first_source_metadata_line_count",
        "simple_call": "simple_call_source_metadata_line_count",
        "sign": "sign_source_metadata_line_count",
    },
    "encoding_signature": {
        "first": "first_encoding_signature",
        "simple_call": "simple_call_encoding_signature",
        "sign": "sign_encoding_signature",
    },
}
OPCODE_IDS = {
    "": 0,
    "TCONST": 1,
    "TMOV": 2,
    "TINV": 3,
    "TADD": 4,
    "TMIN": 5,
    "TMAX": 6,
    "TCMP": 7,
    "TCALL": 8,
    "TLOAD": 9,
    "TSTORE": 10,
    "TRET": 11,
    "TJMP": 12,
    "TBR3": 13,
}
DIRECTIVE_IDS = {
    "": 0,
    ".s3asm": 1,
    ".function": 2,
    ".param": 3,
    ".register": 4,
    ".memory": 5,
    ".label": 6,
    ".end": 7,
    "<blank>": 8,
}
CATEGORY_DIRECTIVE = 0
CATEGORY_INSTRUCTION = 1
CATEGORY_BLANK = 2


def _source() -> str:
    return LINE_ENCODINGS_PATH.read_text(encoding="utf-8")


def _execute(compilation: CompilationResult, entry: str) -> int:
    return Emulator().execute(compilation.assembly, entry=entry)


def _instruction_text(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _line_encoding(line: str) -> dict[str, int]:
    stripped = line.strip()
    if not stripped:
        category = CATEGORY_BLANK
        directive = DIRECTIVE_IDS["<blank>"]
        opcode = ""
        operands: list[str] = []
    elif stripped.startswith("."):
        category = CATEGORY_DIRECTIVE
        directive = DIRECTIVE_IDS[stripped.split()[0]]
        opcode = ""
        operands = ["r"] if directive in {DIRECTIVE_IDS[".param"], DIRECTIVE_IDS[".register"]} else []
    else:
        category = CATEGORY_INSTRUCTION
        directive = DIRECTIVE_IDS[""]
        parts = _instruction_text(line).split()
        opcode = parts[0]
        operands = parts[1:]

    opcode_id = OPCODE_IDS[opcode]
    register_operand_count = sum(1 for operand in operands if operand.startswith("r"))
    has_immediate = int(opcode == "TCONST")
    has_callee = int(opcode == "TCALL")
    has_labels = int(directive == DIRECTIVE_IDS[".label"] or opcode in {"TJMP", "TBR3"})
    has_memory = int(directive == DIRECTIVE_IDS[".memory"] or opcode in {"TLOAD", "TSTORE"})
    has_source = int("; source=" in line)
    score = (
        category
        + opcode_id
        + register_operand_count
        + has_immediate
        + has_callee
        + has_labels
        + has_memory
        + has_source
    )
    return {
        "category": category,
        "directive": directive,
        "opcode": opcode_id,
        "register_operand_count": register_operand_count,
        "has_immediate": has_immediate,
        "has_callee": has_callee,
        "has_labels": has_labels,
        "has_memory": has_memory,
        "has_source": has_source,
        "score": score,
    }


def _derive_line_encoding_metrics(path: Path) -> dict[str, object]:
    encodings = tuple(
        _line_encoding(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    )
    return {
        "encodings": encodings,
        "line_count": len(encodings),
        "encoded_line_count": len(encodings),
        "instruction_count": sum(
            1 for encoding in encodings if encoding["category"] == CATEGORY_INSTRUCTION
        ),
        "directive_count": sum(
            1 for encoding in encodings if encoding["category"] == CATEGORY_DIRECTIVE
        ),
        "blank_count": sum(
            1 for encoding in encodings if encoding["category"] == CATEGORY_BLANK
        ),
        "opcode_count": sum(1 for encoding in encodings if encoding["opcode"] != 0),
        "register_operand_line_count": sum(
            1 for encoding in encodings if encoding["register_operand_count"]
        ),
        "immediate_line_count": sum(
            encoding["has_immediate"] for encoding in encodings
        ),
        "callee_line_count": sum(encoding["has_callee"] for encoding in encodings),
        "label_operand_line_count": sum(
            encoding["has_labels"] for encoding in encodings
        ),
        "memory_operand_line_count": sum(
            encoding["has_memory"] for encoding in encodings
        ),
        "source_metadata_line_count": sum(
            encoding["has_source"] for encoding in encodings
        ),
        "encoding_signature": sum(encoding["score"] for encoding in encodings),
    }


def _lf_normalized_bytes(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def test_renderer_line_content_encoding_model_exists_and_uses_scalar_subset() -> None:
    source = _source()

    assert LINE_ENCODINGS_PATH.is_file()
    assert '"' not in source
    assert "tryte[" not in source
    assert "trit[" not in source
    assert "fn main() -> tryte:" in source
    assert "fn line_content_encoding_model_self_check() -> tryte:" in source
    assert "fn expected_opcode_at(fixture: tryte, index: tryte) -> tryte:" in source
    assert (
        "fn expected_register_operand_count_at(fixture: tryte, index: tryte) -> tryte:"
        in source
    )
    assert "fn expected_line_encoding_score_at(fixture: tryte, index: tryte) -> tryte:" in source


def test_renderer_line_content_encoding_model_compiles() -> None:
    compilation = compile_source(_source())
    names = {function.name for function in compilation.ast.functions}

    assert "main" in names
    assert "line_content_encoding_model_self_check" in names
    assert "validate_all_fixture_line_encodings" in names
    assert "line_encodings_opcode_probe" in names
    assert "line_encodings_signature_probe" in names
    assert "simple_call_line_18_encoding_score" in names
    assert "sign_line_33_has_source_metadata" in names


def test_renderer_line_content_encoding_model_executes_self_check() -> None:
    source = _source()

    assert run_source(source) == 0
    assert run_source(source, entry="line_content_encoding_model_self_check") == 0
    assert run_source(source, entry="validate_all_fixture_line_encodings") == 1


def test_renderer_line_content_encoding_model_metrics_match_current_goldens() -> None:
    compilation = compile_source(_source())
    expected = {
        name: _derive_line_encoding_metrics(path)
        for name, path in GOLDEN_PATHS.items()
    }

    assert expected["first"]["encoding_signature"] == 61
    assert expected["simple_call"]["encoding_signature"] == 73
    assert expected["sign"]["encoding_signature"] == 156

    for metric_name, by_fixture in METRIC_ENTRYPOINTS.items():
        for fixture, entrypoint in by_fixture.items():
            assert _execute(compilation, entrypoint) == expected[fixture][metric_name]


def test_renderer_line_content_encoding_model_key_lines_match_current_goldens() -> None:
    compilation = compile_source(_source())
    expected = {
        name: _derive_line_encoding_metrics(path)
        for name, path in GOLDEN_PATHS.items()
    }

    assert expected["first"]["encodings"][15]["score"] == 9
    assert _execute(compilation, "first_line_15_register_operand_count") == 3
    assert _execute(compilation, "first_line_15_encoding_score") == 9

    assert expected["simple_call"]["encodings"][18]["score"] == 14
    assert _execute(compilation, "simple_call_line_18_register_operand_count") == 3
    assert _execute(compilation, "simple_call_line_18_encoding_score") == 14

    assert expected["sign"]["encodings"][13]["score"] == 17
    assert _execute(compilation, "sign_line_13_register_operand_count") == 1
    assert _execute(compilation, "sign_line_13_encoding_score") == 17

    assert expected["sign"]["encodings"][33]["score"] == 13
    assert _execute(compilation, "sign_line_33_opcode_id") == OPCODE_IDS["TCALL"]
    assert _execute(compilation, "sign_line_33_category_id") == CATEGORY_INSTRUCTION
    assert _execute(compilation, "sign_line_33_register_operand_count") == 2
    assert _execute(compilation, "sign_line_33_has_callee") == 1
    assert _execute(compilation, "sign_line_33_has_source_metadata") == 1
    assert _execute(compilation, "sign_line_33_encoding_score") == 13


def test_renderer_line_content_encoding_model_totals_match_current_goldens() -> None:
    compilation = compile_source(_source())
    metrics = [
        _derive_line_encoding_metrics(path)
        for path in GOLDEN_PATHS.values()
    ]

    assert _execute(compilation, "total_encoded_line_count") == sum(
        metric["encoded_line_count"] for metric in metrics
    )
    assert _execute(compilation, "total_instruction_encoding_count") == sum(
        metric["instruction_count"] for metric in metrics
    )
    assert _execute(compilation, "total_directive_encoding_count") == sum(
        metric["directive_count"] for metric in metrics
    )
    assert _execute(compilation, "total_blank_encoding_count") == sum(
        metric["blank_count"] for metric in metrics
    )
    assert _execute(compilation, "total_opcode_encoding_count") == sum(
        metric["opcode_count"] for metric in metrics
    )
    assert _execute(compilation, "total_register_operand_line_count") == sum(
        metric["register_operand_line_count"] for metric in metrics
    )
    assert _execute(compilation, "total_immediate_line_count") == sum(
        metric["immediate_line_count"] for metric in metrics
    )
    assert _execute(compilation, "total_callee_line_count") == sum(
        metric["callee_line_count"] for metric in metrics
    )
    assert _execute(compilation, "total_label_operand_line_count") == sum(
        metric["label_operand_line_count"] for metric in metrics
    )
    assert _execute(compilation, "total_memory_operand_line_count") == sum(
        metric["memory_operand_line_count"] for metric in metrics
    )
    assert _execute(compilation, "total_source_metadata_line_count") == sum(
        metric["source_metadata_line_count"] for metric in metrics
    )
    assert _execute(compilation, "total_encoding_signature") == sum(
        metric["encoding_signature"] for metric in metrics
    )
    assert _execute(compilation, "line_encodings_totals_probe") == 0


def test_renderer_line_content_encoding_model_executes_fixture_and_shape_probes() -> None:
    compilation = compile_source(_source())

    assert _execute(compilation, "validate_first_line_encodings") == 1
    assert _execute(compilation, "validate_simple_call_line_encodings") == 1
    assert _execute(compilation, "validate_sign_line_encodings") == 1
    assert _execute(compilation, "line_encodings_first_probe") == 0
    assert _execute(compilation, "line_encodings_simple_call_probe") == 0
    assert _execute(compilation, "line_encodings_sign_probe") == 0
    assert _execute(compilation, "line_encodings_unknown_fixture_probe") == 0
    assert _execute(compilation, "line_encodings_unknown_line_probe") == 0
    assert _execute(compilation, "line_encodings_opcode_probe") == 0
    assert _execute(compilation, "line_encodings_flag_probe") == 0
    assert _execute(compilation, "line_encodings_signature_probe") == 0


def test_renderer_line_content_encoding_model_is_registered_for_hosted_check() -> None:
    program = find_program(LINE_ENCODINGS_PATH)

    assert program is not None
    assert program.hosted_expected_return == 0
    assert run_hosted_check(program) == 0


def test_s3_program_check_includes_renderer_line_content_encoding_model() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/s3_program_check.py", "check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert (
        "examples/self_hosting/assembly_renderer_line_encodings.s3"
        in completed.stdout
    )
    assert "s3 program check: checked 13 program(s)" in completed.stdout
    assert "s3 program check: hosted execution checked 10 program(s)" in completed.stdout
    assert "hosted expected return: 0" in completed.stdout
    assert "hosted actual return: 0" in completed.stdout
    assert completed.stderr == ""


def test_renderer_line_content_encoding_model_does_not_enter_output_golden_contracts() -> None:
    assert not Path(
        "tests/golden/inspect/assembly_renderer_line_encodings.assembly.txt"
    ).exists()
    assert not Path(
        "tests/golden/inspect/assembly_renderer_line_encodings.ir.json"
    ).exists()

    actual_outputs = json.loads(
        Path(
            "tests/golden/assembly_renderer_candidate_actual_outputs.json"
        ).read_text(encoding="utf-8")
    )
    assert all(
        output["source"] != LINE_ENCODINGS_PATH.as_posix()
        for output in actual_outputs["outputs"]
    )
    for name, golden_path in GOLDEN_PATHS.items():
        assert _lf_normalized_bytes(ACTUAL_OUTPUT_PATHS[name]) == _lf_normalized_bytes(
            golden_path
        )
