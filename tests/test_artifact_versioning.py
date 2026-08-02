from __future__ import annotations

import json
from pathlib import Path

import pytest

from bootstrap.s3.assembly import (
    ASSEMBLY_FORMAT_VERSION,
    AssemblyParseError,
    parse_assembly,
)
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.ir_serialization import (
    IR_FORMAT_VERSION,
    IRSerializationError,
    deserialize_ir,
    serialize_ir,
)
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.cli import main as cli_main
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).parents[1]


def _legacy_assembly() -> str:
    return """\
.function main -> tryte
    .register r0, tryte
.label entry
    TCONST r0, 6 ; source=2:12:20
    TRET r0
.end
"""


def test_generated_assembly_is_versioned_and_round_trips() -> None:
    assembly = compile_source("fn main() -> tryte:\n    return 6\n").assembly
    rendered = assembly.render()
    assert rendered.startswith(f".s3asm {ASSEMBLY_FORMAT_VERSION}\n\n")
    assert parse_assembly(rendered) == assembly
    assert parse_assembly(rendered).render() == rendered
    assert execute_assembly(rendered) == 6


def test_legacy_assembly_is_normalized_to_current_version() -> None:
    program = parse_assembly(_legacy_assembly())
    assert program.version == ASSEMBLY_FORMAT_VERSION
    assert program.render().startswith(".s3asm 0.5.0\n")
    instruction = program.functions[0].blocks[0].instructions[0]
    assert instruction.source is not None
    assert instruction.source.to_dict() == {
        "offset": 20,
        "line": 2,
        "column": 12,
    }
    assert execute_assembly(program) == 6


@pytest.mark.parametrize(
    ("header", "message"),
    (
        (".s3asm 1.0.0", "incompatible S3 Assembly major version"),
        (".s3asm 0.6.0", "unknown S3 Assembly version"),
        (".s3asm next", "invalid .s3asm version"),
        (".s3asm 0.5", "invalid .s3asm version"),
    ),
)
def test_invalid_or_unknown_assembly_version_is_rejected(
    header: str,
    message: str,
) -> None:
    with pytest.raises(AssemblyParseError, match=message):
        parse_assembly(f"{header}\n{_legacy_assembly()}")


def test_version_directive_must_precede_functions() -> None:
    with pytest.raises(AssemblyParseError, match="must precede all functions"):
        parse_assembly(_legacy_assembly() + ".s3asm 0.5.0\n")


def test_existing_normative_assembly_remains_executable() -> None:
    normative = (ROOT / "examples" / "assembly_recursive_sum.s3asm").read_text(
        encoding="utf-8"
    )
    assert normative.startswith(".s3asm 0.5.0\n")
    assert execute_assembly(normative) == 10
    assert parse_assembly(normative).render() == normative


@pytest.mark.parametrize(
    "filename",
    ("recursive_sum.s3", "static_array.s3", "recursive_memory.s3"),
)
def test_ir_json_round_trip_is_deterministic_and_executable(
    filename: str,
) -> None:
    source = (ROOT / "examples" / filename).read_text(encoding="utf-8")
    original = compile_source(source, mode=SyntaxMode.V0_6).ir
    first = serialize_ir(original)
    second = serialize_ir(original)
    assert first == second
    assert first.endswith("\n")
    assert json.loads(first)["version"] == IR_FORMAT_VERSION
    restored = deserialize_ir(first)
    assert restored == original
    assert serialize_ir(restored) == first
    assert execute_assembly(generate_assembly(restored)) == execute_assembly(
        compile_source(source, mode=SyntaxMode.V0_6).assembly
    )


def test_ir_json_preserves_memory_cfg_and_origins() -> None:
    source = (ROOT / "examples" / "static_array.s3").read_text(encoding="utf-8")
    original = compile_source(source, mode=SyntaxMode.V0_6).ir
    restored = deserialize_ir(serialize_ir(original))
    function = restored.functions[0]
    assert function.memory_objects == original.functions[0].memory_objects
    assert function.blocks == original.functions[0].blocks
    assert function.location == original.functions[0].location
    assert any(
        instruction.location is not None
        for instruction in function.instructions
    )


def test_ir_json_rejects_unknown_version_and_opcode() -> None:
    artifact = json.loads(
        serialize_ir(compile_source("fn main() -> tryte:\n    return 6\n").ir)
    )
    artifact["version"] = "0.7.0"
    with pytest.raises(IRSerializationError, match="unsupported S3 IR version"):
        deserialize_ir(json.dumps(artifact))

    artifact["version"] = IR_FORMAT_VERSION
    artifact["module"]["functions"][0]["blocks"][0]["instructions"][0][
        "opcode"
    ] = "subtract"
    with pytest.raises(IRSerializationError, match="unknown opcode 'subtract'"):
        deserialize_ir(json.dumps(artifact))


def test_ir_json_rejects_missing_unknown_and_invalid_fields() -> None:
    artifact = json.loads(
        serialize_ir(compile_source("fn main() -> tryte:\n    return 6\n").ir)
    )
    del artifact["module"]["functions"][0]["return_type"]
    with pytest.raises(IRSerializationError, match="missing required field"):
        deserialize_ir(json.dumps(artifact))

    artifact = json.loads(
        serialize_ir(compile_source("fn main() -> tryte:\n    return 6\n").ir)
    )
    artifact["module"]["extra"] = True
    with pytest.raises(IRSerializationError, match="unknown field"):
        deserialize_ir(json.dumps(artifact))

    artifact = json.loads(
        serialize_ir(compile_source("fn main() -> tryte:\n    return 6\n").ir)
    )
    artifact["module"]["functions"][0]["registers"][0]["index"] = True
    with pytest.raises(IRSerializationError, match="must be an integer"):
        deserialize_ir(json.dumps(artifact))


def test_ir_json_and_verify_ir_cli_round_trip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact = tmp_path / "static-array.s3ir.json"
    source = ROOT / "examples" / "static_array.s3"
    assert cli_main(["--source-syntax", "0.6", "ir-json", str(source), "-o", str(artifact)]) == 0
    assert capsys.readouterr().err == ""
    payload = artifact.read_text(encoding="utf-8")
    assert payload.endswith("\n")
    assert json.loads(payload)["format"] == "s3-ir"
    assert cli_main(["verify-ir", str(artifact)]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert output.out == "IR verified: 1 function(s)\n"


def test_verify_ir_cli_reports_artifact_error_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact = tmp_path / "future.json"
    artifact.write_text(
        '{"format":"s3-ir","version":"9.0.0","module":{"functions":[]}}\n',
        encoding="utf-8",
    )
    assert cli_main(["verify-ir", str(artifact)]) == 1
    output = capsys.readouterr()
    assert "unsupported S3 IR version" in output.err
    assert "Traceback" not in output.err
