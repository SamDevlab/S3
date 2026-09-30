from __future__ import annotations

import json
import os
import subprocess
import sys
import hashlib
from pathlib import Path

import pytest

from bootstrap.s3 import run_source
from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.assembly_verifier import AssemblyVerifier
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.stage1_artifact import (
    ASSEMBLY_FILENAME,
    HASHES_FILENAME,
    IR_FILENAME,
    MAX_SOURCE_BYTES,
    MANIFEST_FILENAME,
    PROVENANCE_FILENAME,
    Stage1ArtifactError,
    Stage1Rejected,
    Stage1VerificationError,
    build_stage1_artifact,
    compile_stage1_bytes,
)


@pytest.fixture(scope="module")
def stage1_build(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("stage1-build") / "artifact"
    build_stage1_artifact(output)
    return output


def _fresh_runtime(
    repository: Path,
    artifact: Path,
    source: Path,
    output: Path,
) -> subprocess.CompletedProcess[str]:
    source.parent.joinpath("sitecustomize.py").write_text("""\
import sys

BLOCKED = {
    "bootstrap.s3.pipeline",
    "bootstrap.s3.lexer",
    "bootstrap.s3.parser",
    "bootstrap.s3.semantic",
    "bootstrap.s3.lowering",
    "bootstrap.s3.codegen",
    "bootstrap.s3.module_compilation",
    "bootstrap.s3.whole_program",
}

class BlockCompilerModules:
    def find_spec(self, fullname, path=None, target=None):
        if fullname in BLOCKED:
            raise AssertionError(f"reference compiler module imported during Stage1 execution: {fullname}")
        return None

sys.meta_path.insert(0, BlockCompilerModules())
""", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(source.parent), str(repository)))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "bootstrap.s3.stage1_artifact", "compile", str(artifact), str(source), "-o", str(output)],
        cwd=source.parent,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _fresh_build(
    repository: Path,
    output: Path,
    hash_seed: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repository)
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "bootstrap.s3.stage1_artifact", "build", "--output-dir", str(output)],
        cwd=output.parent,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_stage1_build_is_deterministic_and_self_describing(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    first = tmp_path / "build-a"
    second = tmp_path / "build-b"
    first_result = _fresh_build(repository, first, "1")
    second_result = _fresh_build(repository, second, "271828")
    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    first_manifest = json.loads((first / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    second_manifest = json.loads((second / MANIFEST_FILENAME).read_text(encoding="utf-8"))

    assert first_manifest == second_manifest
    for name in (IR_FILENAME, ASSEMBLY_FILENAME, MANIFEST_FILENAME, HASHES_FILENAME, PROVENANCE_FILENAME):
        assert (first / name).read_bytes() == (second / name).read_bytes()

    manifest = json.loads((first / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assembly_summary = json.loads((first / ASSEMBLY_FILENAME).read_text(encoding="utf-8"))
    hashes = json.loads((first / HASHES_FILENAME).read_text(encoding="utf-8"))
    assert manifest["runtime_compiles_source"] is False
    assert manifest["entry_function"] == "stage1_compile_entry"
    assert manifest["artifact"]["sha256"] == first_manifest["artifact"]["sha256"]
    assert manifest["assembly_validation"] == "PASS"
    assert assembly_summary["format"] == "s3-assembly-program-structure-summary"
    assert assembly_summary["canonical_structure_sha256"] == hashes[
        "assembly_program_structure"
    ]["sha256"]
    assert (first / ASSEMBLY_FILENAME).stat().st_size < 512
    source = (
        "fn main() -> i64:\n    return scale(913, 7, 5)\n\n"
        "fn scale(a: i64, b: i64, c: i64) -> i64:\n    return a * (b + c)\n"
    )
    output_a = compile_stage1_bytes(first, source.encode("ascii"))
    output_b = compile_stage1_bytes(second, source.encode("ascii"))
    assert output_a == output_b
    assert run_source(source) == 10956
    assert Emulator().execute(parse_assembly(output_a.decode("ascii"))) == 10956


def test_stage1_manifest_preserves_frozen_source_byte_identity(tmp_path: Path) -> None:
    repository = Path(__file__).parents[1]
    manifest = build_stage1_artifact(tmp_path / "artifact")
    sources = {item["path"]: item for item in manifest["sources"]}
    relative = "selfhost/compiler/stage1_compiler_v1.s3"
    raw = (repository / relative).read_bytes()
    recorded = sources[relative]

    assert len(raw) == recorded["bytes"] == 139740
    assert hashlib.sha256(raw).hexdigest() == recorded["sha256"] == (
        "894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c"
    )


@pytest.mark.parametrize(
    "source, expected",
    (
        ("fn main() -> i64:\n    return 987654321\n", 987654321),
        (
            "fn main() -> i64:\n    return scale(9, 5)\n\nfn scale(a: i64, b: i64) -> i64:\n    return (a + b) * 3\n",
            42,
        ),
        (
            "fn main() -> i64:\n    base: i64 = 40\n    adjustment: i64 = base + 3\n    return adjustment * 2\n",
            86,
        ),
        (
            "fn main() -> i64:\n    return finish()\n\nfn finish() -> i64:\n    return 73\n",
            73,
        ),
        (
            "fn main() -> i64:\n    return merge(31, 12)\n\nfn merge(left: i64, right: i64) -> i64:\n    return left * 2 + right\n",
            74,
        ),
        (
            "fn main() -> i64:\n    return add(multiply(8, 9), 11)\n\nfn multiply(a: i64, b: i64) -> i64:\n    return a * b\n\nfn add(a: i64, b: i64) -> i64:\n    return a + b\n",
            83,
        ),
        (
            "fn main() -> i64:\n    return weighted(4, 5, 6)\n\nfn weighted(a: i64, b: i64, c: i64) -> i64:\n    return a * 100 + b * 10 + c\n",
            456,
        ),
    ),
)
def test_persisted_stage1_compiles_unseen_inputs_in_fresh_process(
    stage1_build: Path,
    tmp_path: Path,
    source: str,
    expected: int,
) -> None:
    repository = Path(__file__).parents[1]
    input_path = tmp_path / "unseen.s3"
    output_path = tmp_path / "unseen.s3asm"
    input_path.write_bytes(source.encode("ascii"))

    result = _fresh_runtime(repository, stage1_build, input_path, output_path)

    assert result.returncode == 0, result.stderr
    assert "STAGE1_COMPILE=PASS" in result.stdout
    assembly_text = output_path.read_text(encoding="ascii")
    assembly = parse_assembly(assembly_text)
    AssemblyVerifier().validate(assembly)
    assert run_source(source) == expected
    assert Emulator().execute(assembly) == expected


def test_stage1_rejection_is_deterministic_and_does_not_publish_output(
    stage1_build: Path,
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[1]
    source_path = tmp_path / "unsupported.s3"
    output_path = tmp_path / "unsupported.s3asm"
    source_path.write_bytes(b"fn main() -> i64:\n    return missing + 1\n")

    first = _fresh_runtime(repository, stage1_build, source_path, output_path)
    second = _fresh_runtime(repository, stage1_build, source_path, output_path)

    assert first.returncode == second.returncode == 1
    assert first.stderr == second.stderr
    assert first.stderr.startswith("S3E_STAGE1_REJECTED phase=")
    assert not output_path.exists()


def test_stage1_cli_reports_input_io_failure_distinctly(
    stage1_build: Path,
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[1]
    missing_source = tmp_path / "missing.s3"
    output_path = tmp_path / "missing.s3asm"

    result = _fresh_runtime(repository, stage1_build, missing_source, output_path)

    assert result.returncode == 2
    assert result.stderr == "S3E_STAGE1_INPUT_IO\n"
    assert not output_path.exists()


def test_stage1_cli_reports_output_io_failure_distinctly(
    stage1_build: Path,
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[1]
    source_path = tmp_path / "valid.s3"
    output_path = tmp_path / "output-directory"
    source_path.write_bytes(b"fn main() -> i64:\n    return 61 + 8\n")
    output_path.mkdir()

    result = _fresh_runtime(repository, stage1_build, source_path, output_path)

    assert result.returncode == 2
    assert result.stderr == "S3E_STAGE1_OUTPUT_IO\n"
    assert output_path.is_dir()


def test_stage1_enforces_source_limit_before_vector_materialization(
    stage1_build: Path,
) -> None:
    with pytest.raises(Stage1Rejected) as rejected:
        compile_stage1_bytes(stage1_build, b" " * (MAX_SOURCE_BYTES + 1))

    assert (rejected.value.phase, rejected.value.error_code) == (1, 1)


def test_stage1_self_source_slice_hits_real_record_result_boundary(
    stage1_build: Path,
) -> None:
    repository = Path(__file__).parents[1]
    raw = (repository / "selfhost/compiler/stage1_compiler_v1.s3").read_bytes()
    start = raw.index(b"fn stage1_empty_ir() -> NativeIR:\n")
    end = raw.index(b"\n\n", start)
    original_function = raw[start:end] + b"\n"
    bounded_program = b"fn main() -> i64:\n    return 0\n\n" + original_function
    assert len(bounded_program) <= MAX_SOURCE_BYTES

    with pytest.raises(Stage1Rejected):
        compile_stage1_bytes(stage1_build, bounded_program)


def test_stage1_self_source_vector_helper_is_rejected_at_signature_boundary(
    stage1_build: Path,
) -> None:
    repository = Path(__file__).parents[1]
    raw = (repository / "selfhost/compiler/stage1_compiler_v1.s3").read_bytes()
    start = raw.index(b"fn stage1_emission_value_count(view: &vector<i64>) -> i64:\n")
    end = raw.index(b"\n\n", start)
    original_function = raw[start:end] + b"\n"
    bounded_program = b"fn main() -> i64:\n    return 0\n\n" + original_function
    assert len(bounded_program) <= MAX_SOURCE_BYTES

    with pytest.raises(Stage1Rejected) as rejected:
        compile_stage1_bytes(stage1_build, bounded_program)

    assert (rejected.value.phase, rejected.value.error_code) == (3, 25)


@pytest.mark.parametrize(
    ("source", "expected", "phase", "error_code"),
    (
        ("fn main() -> i64:\n    return -7\n", -7, 4, 29),
        (
            "fn main() -> i64:\n    mut value: i64 = 5\n    value = value + 2\n    return value\n",
            7,
            4,
            29,
        ),
        ("fn main() -> trit:\n    return 1 < 2\n", -1, 3, 25),
        (
            "fn main() -> i64:\n"
            "    match 1 < 2:\n"
            "        -1:\n"
            "            return 7\n"
            "        0:\n"
            "            return 3\n"
            "        1:\n"
            "            return 1\n",
            7,
            3,
            25,
        ),
        (
            "fn main() -> i64:\n"
            "    mut value: i64 = 0\n"
            "    while value < 3:\n"
            "        value = value + 1\n"
            "    return value\n",
            3,
            3,
            25,
        ),
        (
            "fn main() -> i64:\n"
            "    mut values: vector<i64> = vector_new<i64>(1)\n"
            "    discard vector_push<i64>(&mut values, 9)\n"
            "    return vector_get<i64>(&values, 0)\n",
            9,
            4,
            29,
        ),
        (
            "record Pair:\n"
            "    left: i64\n"
            "    right: i64\n"
            "fn main() -> i64:\n"
            "    mut pair: Pair = Pair(left=4, right=5)\n"
            "    return pair.left + pair.right\n",
            9,
            3,
            25,
        ),
    ),
)
def test_stage1_rejects_reference_supported_features_outside_current_subset(
    stage1_build: Path,
    source: str,
    expected: int,
    phase: int,
    error_code: int,
) -> None:
    assert run_source(source) == expected

    with pytest.raises(Stage1Rejected) as rejected:
        compile_stage1_bytes(stage1_build, source.encode("ascii"))

    assert (rejected.value.phase, rejected.value.error_code) == (phase, error_code)


def test_stage1_artifact_fails_closed_on_ir_digest_mismatch(
    stage1_build: Path,
    tmp_path: Path,
) -> None:
    corrupted = tmp_path / "corrupted"
    corrupted.mkdir()
    (corrupted / MANIFEST_FILENAME).write_bytes((stage1_build / MANIFEST_FILENAME).read_bytes())
    data = bytearray((stage1_build / IR_FILENAME).read_bytes())
    data[-2] ^= 1
    (corrupted / IR_FILENAME).write_bytes(data)

    with pytest.raises(Stage1ArtifactError, match="identity"):
        compile_stage1_bytes(corrupted, b"fn main() -> i64:\n    return 7\n")


def test_stage1_artifact_fails_closed_on_rehashed_invalid_ir(
    stage1_build: Path,
    tmp_path: Path,
) -> None:
    corrupted = tmp_path / "invalid-ir"
    corrupted.mkdir()
    manifest = json.loads((stage1_build / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    data = b"{}"
    manifest["artifact"]["bytes"] = len(data)
    manifest["artifact"]["sha256"] = hashlib.sha256(data).hexdigest()
    (corrupted / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    (corrupted / IR_FILENAME).write_bytes(data)

    with pytest.raises(Stage1VerificationError, match="independent verification"):
        compile_stage1_bytes(corrupted, b"fn main() -> i64:\n    return 7\n")

    repository = Path(__file__).parents[1]
    source_path = tmp_path / "valid.s3"
    output_path = tmp_path / "valid.s3asm"
    source_path.write_bytes(b"fn main() -> i64:\n    return 7\n")
    result = _fresh_runtime(repository, corrupted, source_path, output_path)
    assert result.returncode == 2
    assert result.stderr.startswith("S3E_STAGE1_VERIFY:")
    assert not output_path.exists()
