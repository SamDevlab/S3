from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import subprocess
from types import SimpleNamespace
from pathlib import Path

import pytest

import bootstrap.s3.cli as cli
from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_native_assembly
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.compiler_ng_ir_bridge import decode_ng_ir_events
from bootstrap.s3.diagnostics import S3Error
from bootstrap.s3.compiler_provider import compile_source_set_with_provider
from bootstrap.s3.ffi import build_shared_library_from_assembly
from bootstrap.s3.ir import IRModule
from bootstrap.s3.native_compiler import NativeS3CExecutable, require_s3c_ng_executable
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.project_container import ProjectTooling
from bootstrap.s3.ir_serialization import serialize_ir
from bootstrap.s3.verifier import verify_ir
import tools.native_s3c_ng as native_s3c_ng
from tools.native_s3c_ng import (
    NativeSourceSetResult,
    NativeS3CTransportError,
    build_native_s3c,
    compile_reference_b_ir,
    compiler_source_graph_sha256,
    compiler_source_set,
    run_native_source_set,
    write_s3c_ng_candidate_manifest,
)


_ROOT = Path(__file__).parents[1]


def test_native_source_set_reports_process_failure_before_decoding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = SimpleNamespace(
        executable=tmp_path / "s3c-ng",
        entry_symbol="ng_emit_source_set",
    )
    artifact.executable.write_bytes(b"test executable placeholder")

    def fail_after_partial_output(command: list[str], **kwargs) -> subprocess.CompletedProcess:
        Path(command[3]).write_bytes(b"S3NGOUT1truncated")
        return subprocess.CompletedProcess(
            command,
            returncode=2,
            stdout=b"",
            stderr=b"native S3C-NG transport: EDQUOT while writing output",
        )

    monkeypatch.setattr(native_s3c_ng.subprocess, "run", fail_after_partial_output)
    monkeypatch.setattr(
        native_s3c_ng,
        "decode_output_envelope",
        lambda _encoded: pytest.fail("a failed process envelope must not be decoded"),
    )

    with pytest.raises(NativeS3CTransportError, match="exit=2.*EDQUOT"):
        run_native_source_set(
            artifact,
            {"app.s3": "module app\n"},
            entry_module="app",
        )


_MULTIMODULE_SOURCES = {
    "app.s3": """\
module app
from math import transform as increment
from policy import transform as augment
from decision import choose as choose_value
fn selector() -> i64:
    return 0
fn main() -> i64:
    mut marker: text = text_from_static("app")
    mut total: i64 = increment(1)
    total = total + augment(2)
    total = total + choose_value(selector())
    return total
""",
    "math.s3": """\
module math
export fn transform(value: i64) -> i64:
    mut marker: text = text_from_static("math")
    mut result: i64 = value
    result = result + 1
    return result
""",
    "policy.s3": """\
module policy
export fn transform(value: i64) -> i64:
    mut marker: text = text_from_static("policy")
    return value + 10
""",
    "decision.s3": """\
module decision
export fn choose(value: i64) -> i64:
    mut marker: text = text_from_static("decision")
    match value <=> 0:
        -1:
            return 1
        0:
            return 2
        1:
            return 3
""",
}
_RELATIONAL_MATCH_SOURCES = {
    "app.s3": """\
module app
fn classify(value: i64) -> i64:
    match value > 0:
        -1:
            return 10
        0:
            return 20
        1:
            return 30
fn main() -> i64:
    return classify(2)
""",
}
_INVALID_PROVIDER_SOURCES = {
    "missing-module": {
        "main.s3": "module main\nfrom absent import value\nfn main() -> i64:\n    return value()\n",
    },
    "missing-symbol": {
        "main.s3": "module main\nfrom math import missing\nfn main() -> i64:\n    return missing()\n",
        "math.s3": "module math\nexport fn present() -> i64:\n    return 1\n",
    },
    "wrong-arity": {
        "main.s3": "module main\nfrom math import value\nfn main() -> i64:\n    return value()\n",
        "math.s3": "module math\nexport fn value(argument: i64) -> i64:\n    return argument\n",
    },
    "wrong-argument-type": {
        "main.s3": "module main\nfrom math import value\nfn flag() -> trit:\n    return 1\nfn main() -> i64:\n    return value(flag())\n",
        "math.s3": "module math\nexport fn value(argument: i64) -> i64:\n    return argument\n",
    },
    "private-symbol": {
        "main.s3": "module main\nfrom math import hidden\nfn main() -> i64:\n    return hidden()\n",
        "math.s3": "module math\nfn hidden() -> i64:\n    return 1\n",
    },
    "duplicate-module-identity": {
        "main.s3": "module main\nfn main() -> i64:\n    return 1\n",
        "first.s3": "module math\nexport fn first() -> i64:\n    return 1\n",
        "second.s3": "module math\nexport fn second() -> i64:\n    return 2\n",
    },
    "dependency-cycle": {
        "main.s3": "module main\nfrom helper import value\nfn main() -> i64:\n    return value()\n",
        "helper.s3": "module helper\nfrom main import main as entry\nexport fn value() -> i64:\n    return entry()\n",
    },
    "unknown-reference-field": {
        "app.s3": "module app\nrecord TokenLike:\n    id: i64\nfn read_missing(value: &TokenLike) -> i64:\n    return value.missing\nfn main() -> i64:\n    return 0\n",
    },
    "wrong-bytes-builtin-type": {
        "app.s3": "module app\nfn invalid_index(data: &bytes) -> tryte:\n    return bytes_get(data, data)\nfn main() -> i64:\n    return 0\n",
    },
    "wrong-resource-open-type": {
        "app.s3": "module app\nfn main() -> i64:\n    mut handle: resource_handle = resource_open(1)\n    return 0\n",
    },
}


def _canonical_structure(module: IRModule) -> tuple[object, ...]:
    functions: list[object] = []
    for function in module.functions:
        block_names = {block.name: f"b{index}" for index, block in enumerate(function.blocks)}
        blocks = tuple(
            (
                block_names[block.name],
                tuple(
                    (
                        instruction.opcode.value,
                        None
                        if instruction.opcode.value == "call" and instruction.results
                        else instruction.result,
                        instruction.results,
                        instruction.operands,
                        instruction.immediate,
                        instruction.static_string,
                        instruction.callee,
                        tuple(block_names[target] for target in instruction.targets),
                        instruction.memory,
                        instruction.initialization,
                        instruction.reference_target,
                        instruction.reference_mutable,
                        instruction.reference_is_slice,
                        instruction.slice_length_result,
                        instruction.reference_aggregate,
                        instruction.aggregate_field_paths,
                        instruction.aggregate_field_path,
                    )
                    for instruction in block.instructions
                ),
            )
            for block in function.blocks
        )
        functions.append(
            (
                function.name,
                tuple((param.name, param.register, param.type) for param in function.parameters),
                function.return_type,
                function.result_types,
                tuple((register.index, register.type) for register in function.registers),
                tuple(
                    (memory.index, memory.element_type, memory.length, memory.mutable)
                    for memory in function.memory_objects
                ),
                blocks,
                function.external,
                function.exported,
            )
        )
    return tuple(functions), tuple((item.id, item.value) for item in module.static_strings)


def _source_location_count(module: IRModule) -> int:
    return sum(
        instruction.location is not None
        for function in module.functions
        for block in function.blocks
        for instruction in block.instructions
    )


def _source_location_structure(module: IRModule) -> tuple[object, ...]:
    return tuple(
        (
            function.name,
            function.location,
            tuple(parameter.location for parameter in function.parameters),
            tuple(register.location for register in function.registers),
            tuple(memory.location for memory in function.memory_objects),
            tuple(
                (
                    block.location,
                    tuple(instruction.location for instruction in block.instructions),
                )
                for block in function.blocks
            ),
        )
        for function in module.functions
    )


def _assert_exact_ir_equal(actual: IRModule, expected: IRModule, *, context: str) -> None:
    actual_text = serialize_ir(actual)
    expected_text = serialize_ir(expected)
    if actual_text == expected_text:
        return
    difference = next(
        (
            index
            for index, (actual_char, expected_char) in enumerate(zip(actual_text, expected_text))
            if actual_char != expected_char
        ),
        min(len(actual_text), len(expected_text)),
    )
    start = max(0, difference - 48)
    end = difference + 48
    raise AssertionError(
        f"{context}: canonical IR differs at character {difference}; "
        f"actual={actual_text[start:end]!r}; expected={expected_text[start:end]!r}; "
        f"lengths={len(actual_text)}/{len(expected_text)}"
    )


def _assert_native_compile(
    artifact,
    sources: dict[str, str],
    *,
    expected_result: int,
    tmp_path: Path,
    entry_module: str = "app",
) -> NativeSourceSetResult:
    reference = compile_sources(sources, "O0", entry_module=entry_module).ir
    assert reference is not None

    result = run_native_source_set(artifact, sources, entry_module=entry_module)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert result.status == 0
    actual = decode_ng_ir_events(result.source, result.events)
    verify_ir(actual)
    assert _canonical_structure(actual) == _canonical_structure(reference)
    assert _source_location_structure(actual) == _source_location_structure(reference)
    _assert_exact_ir_equal(actual, reference, context="native compile")

    assembly = generate_native_assembly(generate_assembly(actual))
    executable = NativeToolchain.detect().build(
        assembly,
        tmp_path / f"compiled-{expected_result}",
    )
    completed = NativeToolchain.detect().run(executable)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == f"program returned: {expected_result}\n"
    assert completed.stderr == ""
    return result


def _assert_native_outputs_equal(
    left: NativeSourceSetResult,
    right: NativeSourceSetResult,
    *,
    workload: str,
) -> None:
    assert left.status == right.status, workload
    assert left.source == right.source, workload
    assert left.events == right.events, workload
    assert left.output_envelope_bytes == right.output_envelope_bytes, workload
    assert left.output_envelope_sha256 == right.output_envelope_sha256, workload


def _write_candidate_manifest(artifact, compiler_sources: dict[str, str]) -> None:
    source_commit = subprocess.run(
        ["git", "-C", str(_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()
    toolchain_version = subprocess.run(
        [artifact.toolchain.compiler, "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.splitlines()[0]
    write_s3c_ng_candidate_manifest(
        artifact,
        artifact.executable.with_suffix(".manifest.json"),
        source_commit=source_commit,
        source_graph_sha256=compiler_source_graph_sha256(compiler_sources),
        toolchain_version=toolchain_version,
        bootstrap_parent_ir_sha256=artifact.compiler_ir_sha256,
    )


@pytest.mark.s3_native
@pytest.mark.s3c_ng_promotion
@pytest.mark.skipif(
    not os.environ.get("S3C_NG_BOOTSTRAP_EXECUTABLE"),
    reason="clean-checkout bootstrap artifact is supplied by its dedicated CI job",
)
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="clean S3C-NG bootstrap qualification requires Linux x86-64",
)
def test_native_s3c_ng_clean_checkout_bootstraps_from_exact_head_artifact(
    tmp_path: Path,
) -> None:
    executable_value = os.environ.get("S3C_NG_BOOTSTRAP_EXECUTABLE")
    assert executable_value, "clean-checkout job must provide its pinned bootstrap artifact"
    executable = Path(executable_value)
    candidate = require_s3c_ng_executable(executable)
    manifest_path = executable.with_suffix(".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    sources = compiler_source_set(_ROOT)
    source_commit = subprocess.run(
        ["git", "-C", str(_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()
    source_graph_sha256 = compiler_source_graph_sha256(sources)
    assert manifest["source_commit"] == source_commit
    assert manifest["source_graph_sha256"] == source_graph_sha256
    assert manifest["target"] == "linux-x86_64"
    assert manifest["artifact_sha256"] == hashlib.sha256(executable.read_bytes()).hexdigest()

    generation_c = compile_source_set_with_provider(
        sources,
        compiler="s3c-ng",
        executable=candidate.executable,
        entry_module="app",
    )
    assert generation_c.ir is not None
    verify_ir(generation_c.ir)
    generation_c_sha256 = hashlib.sha256(
        serialize_ir(generation_c.ir).encode("utf-8")
    ).hexdigest()
    assert generation_c_sha256 == manifest["compiler_ir_sha256"]

    artifact_c = build_native_s3c(
        generation_c.ir,
        executable.parent,
        label=executable.name,
    )
    assert artifact_c.assembly_sha256 == manifest["assembly_sha256"]
    assert artifact_c.object_sha256 == manifest["object_sha256"]
    assert artifact_c.executable_sha256 == manifest["artifact_sha256"]
    generation_d = run_native_source_set(
        NativeS3CExecutable(artifact_c.executable, candidate.entry_symbol),
        sources,
        entry_module="app",
    )
    assert generation_d.status == 0
    generation_d_ir = decode_ng_ir_events(generation_d.source, generation_d.events)
    verify_ir(generation_d_ir)
    _assert_exact_ir_equal(generation_d_ir, generation_c.ir, context="clean B-to-C fixed point")
    assert generation_d.source == generation_c.native_result.source
    assert generation_d.events == generation_c.native_result.events
    assert (
        generation_d.output_envelope_sha256
        == generation_c.native_result.output_envelope_sha256
    )


@pytest.mark.s3_native
@pytest.mark.s3c_ng_promotion
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="native S3C-NG qualification requires Linux x86-64",
)
def test_native_s3c_ng_preserves_record_parameter_and_while_locations(
    tmp_path: Path,
) -> None:
    compiler_ir = compile_reference_b_ir(_ROOT)
    artifact = build_native_s3c(compiler_ir, tmp_path / "native-b", label="s3c-ng-b")
    sources = {
        "app.s3": """\
module app
from model import Pair
from model import ScalarBox
from model import classify as imported_classify
from model import make_scalar_box
fn inspect(pair: Pair, limit: i64) -> i64:
    mut index: i64 = 0
    while index < limit:
        index = index + 1
    match index <=> limit:
        -1:
            match index <=> 0:
                -1:
                    return pair.left
                0:
                    index = index
                1:
                    index = index
        0:
            index = index
        1:
            index = index
    return pair.left + pair.inner.value + index
fn relation_result(value: i64) -> trit:
    return value == 1
fn main() -> i64:
    discard imported_classify(0)
    scalar_box: ScalarBox = make_scalar_box()
    mut boxes: vector<ScalarBox> = vector_new<ScalarBox>(1)
    discard vector_push<ScalarBox>(&mut boxes, scalar_box)
    return scalar_box.value - 7 + vector_len<ScalarBox>(&boxes) - 1
""",
        "model.s3": """\
module model
export record Inner:
    value: i64
export record Pair:
    left: i64
    inner: Inner
export record ScalarBox:
    value: i64
export fn classify(value: i64) -> i64:
    match value > 0:
        -1:
            return 10
        0:
            return 20
        1:
            return 30
export fn make_scalar_box() -> ScalarBox:
    return ScalarBox(value=7)
export fn model_value() -> i64:
    return 0
""",
    }
    _assert_native_compile(artifact, sources, expected_result=0, tmp_path=tmp_path)


@pytest.mark.s3_native
@pytest.mark.s3c_ng_promotion
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="native S3C-NG qualification requires Linux x86-64",
)
def test_native_s3c_ng_compiles_bounded_stack_vm_maturity_workload(
    tmp_path: Path,
) -> None:
    from tests.test_language_maturity_workloads import VM_CASES, _vm_program

    compiler_ir = compile_reference_b_ir(_ROOT)
    artifact = build_native_s3c(compiler_ir, tmp_path / "native-b", label="s3c-ng-b")
    _write_candidate_manifest(artifact, compiler_source_set(_ROOT))
    sources = {"main.s3": _vm_program(VM_CASES)}

    result = _assert_native_compile(
        artifact,
        sources,
        expected_result=0,
        entry_module="main",
        tmp_path=tmp_path,
    )
    assert result.status == 0


@pytest.mark.s3_native
@pytest.mark.s3c_ng_promotion
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="native S3C-NG qualification requires Linux x86-64",
)
def test_native_s3c_ng_matches_existing_language_maturity_workloads(
    tmp_path: Path,
) -> None:
    from tests.test_language_maturity_workloads import (
        _csv_program,
        _hex_program,
        _ordering_program,
    )

    compiler_ir = compile_reference_b_ir(_ROOT)
    artifact = build_native_s3c(compiler_ir, tmp_path / "native-b", label="s3c-ng-b")
    _write_candidate_manifest(artifact, compiler_source_set(_ROOT))
    workloads = (
        (
            "ordering-search",
            _ordering_program((29, -4, 8, 8, 17, 0), (-4, 8, 17, 30)),
        ),
        (
            "hex-encoding",
            _hex_program(bytes((0, 83, 51, 255))),
        ),
        (
            "csv-integer-parser",
            {"main.s3": _csv_program("-12,0,25,-3", (10, 4))},
        ),
    )

    for name, sources in workloads:
        work_directory = tmp_path / name
        work_directory.mkdir()
        result = _assert_native_compile(
            artifact,
            sources,
            expected_result=0,
            entry_module="main",
            tmp_path=work_directory,
        )
        assert result.status == 0, name


@pytest.mark.s3_native
@pytest.mark.s3c_ng_promotion
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="native S3C-NG qualification requires Linux x86-64",
)
def test_native_s3c_ng_rejects_reference_invalid_programs_without_fallback(
    tmp_path: Path,
) -> None:
    compiler_ir = compile_reference_b_ir(_ROOT)
    artifact = build_native_s3c(compiler_ir, tmp_path / "native-b", label="s3c-ng-b")
    _write_candidate_manifest(artifact, compiler_source_set(_ROOT))
    expected_statuses = {
        "missing-module": -3,
        "missing-symbol": -4,
        "wrong-arity": -14,
        "wrong-argument-type": -14,
        "private-symbol": -5,
        "duplicate-module-identity": -2,
        "dependency-cycle": -6,
        "unknown-reference-field": -15,
        "wrong-bytes-builtin-type": -14,
        "wrong-resource-open-type": -14,
    }

    for case, sources in _INVALID_PROVIDER_SOURCES.items():
        entry_module = (
            "main"
            if case in {
                "missing-module",
                "missing-symbol",
                "wrong-arity",
                "wrong-argument-type",
                "private-symbol",
                "duplicate-module-identity",
                "dependency-cycle",
            }
            else "app"
        )
        with pytest.raises(S3Error):
            compile_sources(sources, entry_module=entry_module)

        with pytest.raises(
            NativeS3CTransportError,
            match=rf"rejected the source set \(status={expected_statuses[case]}\)",
        ):
            compile_source_set_with_provider(
                sources,
                compiler="s3c-ng",
                executable=artifact.executable,
                entry_module=entry_module,
            )


@pytest.mark.s3_native
@pytest.mark.s3c_ng_promotion
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="native S3C-NG FFI qualification requires Linux x86-64",
)
def test_native_s3c_ng_ffi_build_uses_selected_compiler_and_matches_reference(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiler_ir = compile_reference_b_ir(_ROOT)
    artifact = build_native_s3c(compiler_ir, tmp_path / "native-b", label="s3c-ng-b")
    _write_candidate_manifest(artifact, compiler_source_set(_ROOT))

    source = """\
export fn add(a: i64, b: i64) -> i64:
    return a + b
export fn multiply(a: f64, b: f64) -> f64:
    return a * b
fn main() -> i64:
    return 0
"""
    source_path = tmp_path / "ffi.s3"
    source_path.write_text(source, encoding="utf-8")

    def reject_python_fallback(*_args, **_kwargs):
        pytest.fail("explicit S3C-NG CLI command fell back to compile_source")

    monkeypatch.setattr(cli, "compile_source", reject_python_fallback)

    ng_library = tmp_path / "libffi-ng.so"
    assert cli.main(
        [
            "ffi-build",
            str(source_path),
            "--compiler",
            "s3c-ng",
            "--s3c-ng-executable",
            str(artifact.executable),
            "--output",
            str(ng_library),
        ]
    ) == 0
    capsys.readouterr()

    test_manifest = tmp_path / "s3-test.toml"
    test_manifest.write_text(
        '[runner]\nmode = "hosted"\ntimeout_ms = 10000\n\n'
        '[[test]]\nname = "ffi_source_main"\nsource = "ffi.s3"\nexpected = 0\n',
        encoding="utf-8",
    )
    report_path = tmp_path / "s3-test-report.json"
    assert cli.main(
        [
            "test",
            str(test_manifest),
            "--compiler",
            "s3c-ng",
            "--s3c-ng-executable",
            str(artifact.executable),
            "--report",
            str(report_path),
        ]
    ) == 0
    test_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert test_report["compiler"] == "s3c-ng"
    assert test_report["summary"]["status"] == "PASS"
    assert test_report["summary"]["passed"] == 1

    reference_library = tmp_path / "libffi-python.so"
    reference_ir = compile_sources({"main.s3": source}, entry_module="main").ir
    assert reference_ir is not None
    reference_assembly = generate_assembly(reference_ir)
    from bootstrap.s3.ffi import build_shared_library_from_assembly

    build_shared_library_from_assembly(reference_assembly, reference_library)

    def call_exports(path: Path) -> tuple[int, float]:
        library = ctypes.CDLL(str(path))
        add = getattr(library, "__s3mod_main__add")
        multiply = getattr(library, "__s3mod_main__multiply")
        add.argtypes = [ctypes.c_int64, ctypes.c_int64]
        add.restype = ctypes.c_int64
        multiply.argtypes = [ctypes.c_double, ctypes.c_double]
        multiply.restype = ctypes.c_double
        return (
            add(2, 5),
            multiply(1.5, 4.0),
        )

    ng_results = call_exports(ng_library)
    reference_results = call_exports(reference_library)
    assert ng_results == reference_results == (7, 6.0)

    slice_source = """\
export fn sum(xs: &[i64]) -> i64:
    return xs[0] + xs[1]
export fn relay(xs: &[i64]) -> i64:
    return sum(xs)
fn main() -> i64:
    return 0
"""
    slice_source_path = tmp_path / "ffi-slices.s3"
    slice_source_path.write_text(slice_source, encoding="utf-8")
    ng_slice_library = tmp_path / "libffi-slices-ng.so"
    assert cli.main(
        [
            "ffi-build",
            str(slice_source_path),
            "--compiler",
            "s3c-ng",
            "--s3c-ng-executable",
            str(artifact.executable),
            "--output",
            str(ng_slice_library),
        ]
    ) == 0
    capsys.readouterr()

    slice_reference_ir = compile_sources(
        {"main.s3": slice_source}, entry_module="main"
    ).ir
    assert slice_reference_ir is not None
    slice_reference_library = tmp_path / "libffi-slices-python.so"
    build_shared_library_from_assembly(
        generate_assembly(slice_reference_ir), slice_reference_library
    )

    def call_slice_exports(path: Path) -> tuple[int, int]:
        library = ctypes.CDLL(str(path))
        total = getattr(library, "__s3mod_main__sum")
        relay = getattr(library, "__s3mod_main__relay")
        total.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_int64]
        total.restype = ctypes.c_int64
        relay.argtypes = total.argtypes
        relay.restype = ctypes.c_int64
        values = (ctypes.c_int64 * 2)(13, 29)
        return total(values, len(values)), relay(values, len(values))

    assert call_slice_exports(ng_slice_library) == call_slice_exports(
        slice_reference_library
    ) == (42, 42)

    mutable_slice_source = """\
export fn bump(xs: &mut [i64]) -> i64:
    xs[0] = xs[0] + 1
    return xs[0]
fn main() -> i64:
    return 0
"""
    mutable_slice_path = tmp_path / "ffi-mutable-slice.s3"
    mutable_slice_path.write_text(mutable_slice_source, encoding="utf-8")
    rejected = cli.main(
        [
            "ffi-build",
            str(mutable_slice_path),
            "--compiler",
            "s3c-ng",
            "--s3c-ng-executable",
            str(artifact.executable),
            "--output",
            str(tmp_path / "libffi-mutable-slice-ng.so"),
        ]
    )
    assert rejected == 1
    assert "S3C-NG rejected the source set" in capsys.readouterr().err


@pytest.mark.s3_native
@pytest.mark.s3c_ng_promotion
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="native S3C-NG qualification requires Linux x86-64",
)
def test_native_s3c_ng_reaches_native_compiler_fixed_point(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compiler_ir = compile_reference_b_ir(_ROOT)
    artifact_b = build_native_s3c(compiler_ir, tmp_path / "native-b", label="compiler")
    assert artifact_b.compiler_ir_sha256
    assert artifact_b.assembly_sha256
    assert artifact_b.object_sha256
    assert artifact_b.executable_bytes > 0
    assert artifact_b.executable.read_bytes()[:4] == b"\x7fELF"
    assert artifact_b.executable.read_bytes()[16:18] == b"\x02\x00"

    small = {
        "app.s3": (
            "module app\n"
            "fn answer(value: i64) -> i64:\n"
            "    return value\n"
            "fn main() -> i64:\n"
            "    return answer(42)\n"
        ),
    }
    compiler_sources = compiler_source_set(_ROOT)
    _write_candidate_manifest(artifact_b, compiler_sources)

    provider_output = compile_source_set_with_provider(
        small,
        compiler="s3c-ng",
        executable=artifact_b.executable,
        entry_module="app",
    )
    reference_output = compile_sources(small, entry_module="app")
    assert reference_output.ir is not None
    assert serialize_ir(provider_output.ir) == serialize_ir(reference_output.ir)
    assert provider_output.assembly.render() == generate_assembly(reference_output.ir).render()

    cli_source_path = tmp_path / "provider-cli" / "main.s3"
    cli_source_path.parent.mkdir(parents=True, exist_ok=True)
    cli_source_path.write_text(small["app.s3"], encoding="utf-8", newline="\n")

    def reject_python_fallback(*_args, **_kwargs):
        pytest.fail("explicit S3C-NG CLI command fell back to compile_source")

    monkeypatch.setattr(cli, "compile_source", reject_python_fallback)

    def run_ng_cli(*arguments: str) -> str:
        result = cli.main(
            [
                *arguments,
                "--compiler",
                "s3c-ng",
                "--s3c-ng-executable",
                str(artifact_b.executable),
                "--entry-module",
                "app",
            ]
        )
        captured = capsys.readouterr()
        assert result == 0, f"CLI failed for {arguments}: {captured.err}"
        assert captured.err == ""
        return captured.out

    assert "status: ok" in run_ng_cli("check", str(cli_source_path))
    assert run_ng_cli("ir", str(cli_source_path)) == json.dumps(
        reference_output.ir.to_dict(), indent=2
    ) + "\n"
    assert run_ng_cli("ir-json", str(cli_source_path)) == serialize_ir(
        reference_output.ir
    )
    inspection = run_ng_cli("inspect", str(cli_source_path), "--emit", "summary")
    assert "functions: 2" in inspection
    assert "entry: main" in inspection
    assert run_ng_cli("inspect", str(cli_source_path), "--emit", "ir").endswith(
        json.dumps(reference_output.ir.to_dict(), indent=2) + "\n"
    )
    assert run_ng_cli("asm", str(cli_source_path)) == reference_output.assembly_text
    assert run_ng_cli("run", str(cli_source_path)) == "program returned: 42\n"
    expected_native_assembly = generate_native_assembly(
        generate_assembly(reference_output.ir)
    )
    assert run_ng_cli("native-asm", str(cli_source_path)) == expected_native_assembly

    built_executable = tmp_path / "provider-cli" / "built-program"
    assert run_ng_cli(
        "build", str(cli_source_path), "--output", str(built_executable)
    ).strip() == str(built_executable)
    built_result = NativeToolchain.detect().run(built_executable)
    assert built_result.returncode == 0
    assert built_result.stdout == "program returned: 42\n"
    assert built_result.stderr == ""
    assert run_ng_cli("run-native", str(cli_source_path)) == "program returned: 42\n"

    project_root = tmp_path / "project-tooling"
    project_source_root = project_root / "src"
    project_source_root.mkdir(parents=True)
    project_source = """\
module main
fn increment(value: i64) -> i64:
    return value + 1
fn main() -> i64:
    return increment(41)
"""
    (project_source_root / "main.s3").write_text(
        project_source, encoding="utf-8", newline="\n"
    )
    (project_root / "s3.toml").write_text(
        "[project]\nname='promotion-project'\nversion='1'\n"
        "entrypoint='main'\nsource_roots=['src']\nprofile='hosted'\n",
        encoding="ascii",
    )
    python_project = ProjectTooling(project_root)
    ng_project = ProjectTooling(
        project_root, compiler="s3c-ng", executable=artifact_b.executable
    )
    python_project_ir = python_project.build().ir
    ng_project_ir = ng_project.build().ir
    assert python_project_ir is not None
    assert ng_project_ir is not None
    assert serialize_ir(ng_project_ir) == serialize_ir(python_project_ir)
    assert python_project.run() == ng_project.run() == 42

    for workload_name, sources, expected_result in (
        ("relational-match", _RELATIONAL_MATCH_SOURCES, 10),
        ("multimodule", _MULTIMODULE_SOURCES, 16),
    ):
        workload_directory = tmp_path / "provider-cli" / workload_name
        workload_directory.mkdir(parents=True)
        for logical_path, contents in sources.items():
            source_path = workload_directory / logical_path
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(contents, encoding="utf-8", newline="\n")

        reference = compile_sources(sources, entry_module="app")
        assert reference.ir is not None
        assert run_ng_cli("ir-json", str(workload_directory)) == serialize_ir(
            reference.ir
        )
        expected_output = f"program returned: {expected_result}\n"
        assert run_ng_cli("run", str(workload_directory)) == expected_output

        workload_executable = workload_directory / "program"
        assert run_ng_cli(
            "build",
            str(workload_directory),
            "--output",
            str(workload_executable),
        ).strip() == str(workload_executable)
        workload_result = NativeToolchain.detect().run(workload_executable)
        assert workload_result.returncode == 0
        assert workload_result.stdout == expected_output
        assert workload_result.stderr == ""
        assert run_ng_cli("run-native", str(workload_directory)) == expected_output

    b_small = _assert_native_compile(
        artifact_b, small, expected_result=42, tmp_path=tmp_path
    )
    b_relational_match = _assert_native_compile(
        artifact_b,
        _RELATIONAL_MATCH_SOURCES,
        expected_result=10,
        tmp_path=tmp_path,
    )

    b_multimodule = _assert_native_compile(
        artifact_b,
        _MULTIMODULE_SOURCES,
        expected_result=16,
        tmp_path=tmp_path,
    )

    compiler_source_bytes = sum(len(source.encode("utf-8")) for source in compiler_sources.values())
    native_b_to_c = run_native_source_set(
        artifact_b,
        compiler_sources,
        entry_module="app",
        timeout=900.0,
    )
    assert native_b_to_c.returncode == 0, native_b_to_c.stderr.decode(errors="replace")
    assert native_b_to_c.status == 0
    generation_c = decode_ng_ir_events(native_b_to_c.source, native_b_to_c.events)
    verify_ir(generation_c)
    assert len(compiler_sources) == 8
    assert compiler_source_bytes > 0
    assert len(generation_c.functions) == len(compiler_ir.functions)
    assert _canonical_structure(generation_c) == _canonical_structure(compiler_ir)
    assert _source_location_structure(generation_c) == _source_location_structure(
        compiler_ir
    )
    _assert_exact_ir_equal(generation_c, compiler_ir, context="B-to-C compiler IR")

    artifact_c = build_native_s3c(generation_c, tmp_path / "native-c", label="compiler")
    c_small = _assert_native_compile(
        artifact_c, small, expected_result=42, tmp_path=tmp_path
    )
    c_relational_match = _assert_native_compile(
        artifact_c,
        _RELATIONAL_MATCH_SOURCES,
        expected_result=10,
        tmp_path=tmp_path,
    )
    c_multimodule = _assert_native_compile(
        artifact_c,
        _MULTIMODULE_SOURCES,
        expected_result=16,
        tmp_path=tmp_path,
    )
    from tests.test_language_maturity_workloads import _ordering_program

    ordering_sources = _ordering_program(
        (29, -4, 8, 8, 17, 0),
        (-4, 8, 17, 30),
    )
    b_ordering = _assert_native_compile(
        artifact_b,
        ordering_sources,
        expected_result=0,
        tmp_path=tmp_path,
        entry_module="main",
    )
    c_ordering = _assert_native_compile(
        artifact_c,
        ordering_sources,
        expected_result=0,
        tmp_path=tmp_path,
        entry_module="main",
    )
    _assert_native_outputs_equal(
        b_small, c_small, workload="B/C small program"
    )
    _assert_native_outputs_equal(
        b_relational_match,
        c_relational_match,
        workload="B/C relational match control-flow program",
    )
    _assert_native_outputs_equal(
        b_multimodule,
        c_multimodule,
        workload="B/C multi-module program",
    )
    _assert_native_outputs_equal(
        b_ordering,
        c_ordering,
        workload="B/C insertion-sort and binary-search maturity workload",
    )

    native_c_to_d = run_native_source_set(
        artifact_c,
        compiler_sources,
        entry_module="app",
        timeout=900.0,
    )
    assert native_c_to_d.returncode == 0, native_c_to_d.stderr.decode(errors="replace")
    assert native_c_to_d.status == 0
    generation_d = decode_ng_ir_events(native_c_to_d.source, native_c_to_d.events)
    verify_ir(generation_d)
    assert _canonical_structure(generation_d) == _canonical_structure(generation_c)
    _assert_exact_ir_equal(generation_d, generation_c, context="C-to-D fixed point")
    _assert_exact_ir_equal(generation_c, compiler_ir, context="host-to-C fixed point")
    assert native_c_to_d.output_envelope_sha256 == native_b_to_c.output_envelope_sha256
    assert native_c_to_d.output_envelope_bytes == native_b_to_c.output_envelope_bytes

    artifact_b_repeat = build_native_s3c(
        compiler_ir,
        tmp_path / "native-b-repeat",
        label="compiler",
    )
    artifact_c_repeat = build_native_s3c(
        generation_c,
        tmp_path / "native-c-repeat",
        label="compiler",
    )
    assert artifact_b_repeat.assembly_sha256 == artifact_b.assembly_sha256
    assert artifact_b_repeat.object_sha256 == artifact_b.object_sha256
    assert artifact_b_repeat.executable_sha256 == artifact_b.executable_sha256
    assert artifact_c_repeat.assembly_sha256 == artifact_c.assembly_sha256
    assert artifact_c_repeat.object_sha256 == artifact_c.object_sha256
    assert artifact_c_repeat.executable_sha256 == artifact_c.executable_sha256
    assert artifact_b.object_path.name == artifact_c.object_path.name == "compiler.o"
    assert artifact_b.assembly.encode() == artifact_c.assembly.encode()
    assert artifact_b.object_path.read_bytes() == artifact_c.object_path.read_bytes()
    assert artifact_b.executable.read_bytes() == artifact_c.executable.read_bytes()

    hosted_serialized = serialize_ir(compiler_ir).encode("utf-8")
    native_serialized = serialize_ir(generation_c).encode("utf-8")
    assembly_equal = artifact_c.assembly_sha256 == artifact_b.assembly_sha256
    object_equal = artifact_c.object_sha256 == artifact_b.object_sha256
    elf_equal = artifact_c.executable_sha256 == artifact_b.executable_sha256
    print(f"NATIVE_B_ELF_SHA256={artifact_b.executable_sha256}")
    print(f"NATIVE_C_ELF_SHA256={artifact_c.executable_sha256}")
    print(f"NATIVE_B_TO_C_OUTPUT_SHA256={native_b_to_c.output_envelope_sha256}")
    print(f"NATIVE_C_TO_D_OUTPUT_SHA256={native_c_to_d.output_envelope_sha256}")
    print("NATIVE_B_TO_C_C_TO_D_OUTPUT_BYTE_EQUAL=True")
    print(f"NATIVE_COMPILER_SOURCE_MODULES={len(compiler_sources)}")
    print(f"NATIVE_COMPILER_SOURCE_BYTES={compiler_source_bytes}")
    print(f"NATIVE_COMPILER_SOURCE_FUNCTIONS={len(generation_c.functions)}")
    print(f"HOSTED_REFERENCE_IR_SHA256={hashlib.sha256(hosted_serialized).hexdigest()}")
    print(f"NATIVE_C_IR_SHA256={hashlib.sha256(native_serialized).hexdigest()}")
    print(f"HOSTED_REFERENCE_SOURCE_LOCATIONS={_source_location_count(compiler_ir)}")
    print(f"NATIVE_C_SOURCE_LOCATIONS={_source_location_count(generation_c)}")
    print(f"HOSTED_NATIVE_SERIALIZED_IR_EQUAL={hosted_serialized == native_serialized}")
    print(
        "B_C_SOURCE_LOCATION_AND_CANONICAL_SERIALIZATION_EQUAL="
        f"{hosted_serialized == native_serialized}"
    )
    print(f"NATIVE_B_TO_C_SECONDS={native_b_to_c.elapsed_seconds:.6f}")
    print(f"NATIVE_C_TO_D_SECONDS={native_c_to_d.elapsed_seconds:.6f}")
    print(f"B_REPEAT_ASSEMBLY_OBJECT_ELF_EQUAL=True")
    print(f"C_REPEAT_ASSEMBLY_OBJECT_ELF_EQUAL=True")
    print(f"ASSEMBLY_SHA256_EQUAL={assembly_equal}")
    print(f"OBJECT_SHA256_EQUAL={object_equal}")
    print(f"ELF_SHA256_EQUAL={elf_equal}")
    print(
        "B_C_ASSEMBLY_TEXT_BYTE_IDENTICAL="
        f"{artifact_b.assembly.encode() == artifact_c.assembly.encode()}"
    )
    print(
        "B_C_OBJECT_BYTE_IDENTICAL="
        f"{artifact_b.object_path.read_bytes() == artifact_c.object_path.read_bytes()}"
    )
    print(
        "B_C_ELF_BYTE_IDENTICAL="
        f"{artifact_b.executable.read_bytes() == artifact_c.executable.read_bytes()}"
    )
    print("ASSEMBLY_DIFFERENCE_CLASS=SOURCE_LOCATION_DIAGNOSTIC_METADATA")
