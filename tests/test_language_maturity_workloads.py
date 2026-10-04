from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

import pytest

from bootstrap.s3.backends.x86_64.backend import X8664Backend
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source, compile_sources


ROOT = Path(__file__).resolve().parents[1]
WORKLOADS_DIR = ROOT / "examples" / "language_maturity"
ORDERING_SOURCE = WORKLOADS_DIR / "insertion_sort_search.s3"
HEX_SOURCE = WORKLOADS_DIR / "hex_encode.s3"
CSV_SOURCE = WORKLOADS_DIR / "csv_integer_parser.s3"
VM_SOURCE = WORKLOADS_DIR / "bounded_stack_vm.s3"
PEBBLE_SOURCE = WORKLOADS_DIR / "pebble_compiler.s3"


def _ordering_program(values: tuple[int, ...], targets: tuple[int, ...]) -> dict[str, str]:
    lines = [
        "module main",
        "from s3.workloads.ordering import insertion_sort",
        "from s3.workloads.ordering import binary_search",
        "fn main() -> i64:",
        f"    mut values: i64_vector = i64_vector_new({len(values)})",
    ]
    lines.extend(f"    discard i64_vector_push(&mut values, {value})" for value in values)
    lines.extend(
        [
            "    mut failures: i64 = 0",
            "    discard insertion_sort(&mut values)",
            f"    mut index: i64 = 1",
            f"    while index < i64_vector_len(&values):",
            "        mut previous: i64 = i64_vector_get(&values, index - 1)",
            "        mut current: i64 = i64_vector_get(&values, index)",
            "        match previous > current:",
            "            -1:",
            "                failures = failures + 1",
            "            0:",
            "                failures = failures",
            "            1:",
            "                failures = failures",
            "        index = index + 1",
        ]
    )
    ordered = sorted(values)
    for target in targets:
        expected = ordered.index(target) if target in ordered else -1
        lines.extend(
            [
                f"    failures = failures + mismatch_index(binary_search(&values, {target}), {expected})",
            ]
        )
    lines.extend(
        [
            "    return failures",
            "fn mismatch_index(actual: i64, expected: i64) -> i64:",
            "    match actual == expected:",
            "        -1:",
            "            return 0",
            "        0:",
            "            return 1",
            "        1:",
            "            return 1",
        ]
    )
    main = "\n".join(lines) + "\n"
    return {"main.s3": main, "s3/workloads/ordering.s3": ORDERING_SOURCE.read_text(encoding="utf-8")}


@pytest.mark.parametrize(
    ("values", "targets"),
    [
        ((29, -4, 8, 8, 17, 0), (-4, 8, 17, 30)),
        ((3, 1, 2), (1, 2, 3, 0)),
        ((-9, -7, -5, -3), (-9, -6, -3)),
        ((6, 5, 4, 3, 2, 1), (1, 4, 6, 7)),
        ((), (0,)),
    ],
)
@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_ordering_workload_sorts_and_searches_runtime_vector(values, targets, optimization) -> None:
    compilation = compile_sources(
        _ordering_program(values, targets), optimization=optimization, entry_module="main"
    )
    assert execute_ir(compilation.ir) == 0


def test_ordering_workload_native_lowering_uses_general_vector_operations() -> None:
    compilation = compile_sources(
        _ordering_program((5, -2, 7, 0), (-2, 0, 5, 7, 9)),
        optimization=OptimizationLevel.O1,
        entry_module="main",
    )
    native = X8664Backend().generate(compilation.assembly)
    assert "__s3_builtin_i64_vector_new" in native
    assert "__s3_builtin_i64_vector_get" in native
    assert "__s3_builtin_i64_vector_set" in native


def _hex_program(payload: bytes) -> dict[str, str]:
    expected = payload.hex().encode("ascii")
    lines = [
        "module main",
        "from s3.workloads.encoding import hex_encode",
        "fn main() -> i64:",
        f"    mut input: bytes = bytes_new({len(payload)})",
    ]
    lines.extend(f"    discard bytes_push(&mut input, {octet})" for octet in payload)
    lines.extend(
        [
            "    mut encoded: bytes = hex_encode(&input)",
            f"    mut failures: i64 = mismatch_index(bytes_len(&encoded), {len(expected)})",
        ]
    )
    for index, octet in enumerate(expected):
        lines.append(
            f"    failures = failures + mismatch_index(to_i64(bytes_get(&encoded, {index})), {octet})"
        )
    lines.extend(
        [
            "    return failures",
            "fn mismatch_index(actual: i64, expected: i64) -> i64:",
            "    match actual == expected:",
            "        -1:",
            "            return 0",
            "        0:",
            "            return 1",
            "        1:",
            "            return 1",
        ]
    )
    return {
        "main.s3": "\n".join(lines) + "\n",
        "s3/workloads/encoding.s3": HEX_SOURCE.read_text(encoding="utf-8"),
    }


@pytest.mark.parametrize(
    "payload",
    [b"", b"S3", bytes((0, 1, 15, 16, 127, 128, 254, 255)), b"embedded\x00byte"],
)
@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_hex_encoding_runs_on_runtime_bytes(payload, optimization) -> None:
    compilation = compile_sources(
        _hex_program(payload), optimization=optimization, entry_module="main"
    )
    assert execute_ir(compilation.ir) == 0


def test_hex_encoding_native_lowering_uses_general_byte_operations() -> None:
    compilation = compile_sources(
        _hex_program(bytes((0, 127, 128, 255))),
        optimization=OptimizationLevel.O1,
        entry_module="main",
    )
    native = X8664Backend().generate(compilation.assembly)
    assert "__s3_builtin_bytes_new" in native
    assert "__s3_builtin_bytes_get" in native
    assert "__s3_builtin_bytes_push" in native


def _csv_program(source_text: str, expected: tuple[int, int] | None) -> str:
    source = CSV_SOURCE.read_text(encoding="utf-8")
    main = [
        "fn main() -> i64:",
        f'    mut input: text = text_from_static("{source_text}")',
        "    mut parsed: CsvParse = parse_csv_integers(&input)",
    ]
    if expected is None:
        main.extend(
            [
                "    match parsed.valid <=> 0:",
                "        -1:",
                "            return 1",
                "        0:",
                "            return 0",
                "        1:",
                "            return 1",
            ]
        )
    else:
        expected_sum, expected_count = expected
        main.extend(
            [
                "    match parsed.valid <=> -1:",
                "        -1:",
                "            return 1",
                "        0:",
                f"            return mismatch_index(parsed.total, {expected_sum}) + mismatch_index(parsed.count, {expected_count})",
                "        1:",
                "            return 1",
            ]
        )
    main.extend(
        [
            "fn mismatch_index(actual: i64, expected: i64) -> i64:",
            "    match actual == expected:",
            "        -1:",
            "            return 0",
            "        0:",
            "            return 1",
            "        1:",
            "            return 1",
        ]
    )
    return source + "\n" + "\n".join(main) + "\n"


@pytest.mark.parametrize(
    ("source_text", "expected"),
    [
        ("1,2,3", (6, 3)),
        ("-12,0,25,-3", (10, 4)),
        ("7", (7, 1)),
        ("", None),
        ("1,,2", None),
        ("-,2", None),
        ("1,2,", None),
    ],
)
@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_csv_parser_processes_runtime_text(source_text, expected, optimization) -> None:
    compilation = compile_source(
        _csv_program(source_text, expected), optimization=optimization
    )
    assert execute_ir(compilation.ir) == 0


def _vm_program(cases: tuple[tuple[tuple[int, ...], int | None], ...]) -> str:
    source = VM_SOURCE.read_text(encoding="utf-8")
    lines = [
        "fn main() -> i64:",
        "    mut failures: i64 = 0",
    ]
    for index, (bytecode, expected) in enumerate(cases):
        program = f"program_{index}"
        first = f"first_{index}"
        second = f"second_{index}"
        lines.append(f"    mut {program}: i64_vector = i64_vector_new({len(bytecode)})")
        lines.extend(
            f"    discard i64_vector_push(&mut {program}, {word})" for word in bytecode
        )
        lines.extend(
            [
                f"    mut {first}: VmResult = run_vm(&{program})",
                f"    mut {second}: VmResult = run_vm(&{program})",
            ]
        )
        if expected is None:
            lines.extend(
                [
                    f"    match {first}.valid <=> 0:",
                    "        -1:",
                    "            failures = failures + 1",
                    "        0:",
                    "            failures = failures",
                    "        1:",
                    "            failures = failures + 1",
                ]
            )
        else:
            lines.extend(
                [
                    f"    match {first}.valid <=> -1:",
                    "        -1:",
                    "            failures = failures + 1",
                    "        0:",
                    f"            failures = failures + mismatch_index({first}.value, {expected}) + mismatch_index({second}.value, {expected})",
                    "        1:",
                    "            failures = failures + 1",
                ]
            )
    lines.append("    return failures")
    lines.extend(
        [
            "fn mismatch_index(actual: i64, expected: i64) -> i64:",
            "    match actual == expected:",
            "        -1:",
            "            return 0",
            "        0:",
            "            return 1",
            "        1:",
            "            return 1",
        ]
    )
    return source + "\n" + "\n".join(lines) + "\n"


VM_CASES = (
    ((-1, 7, -1, 5, 1, -1, 0), 12),
    ((-1, 20, -1, 8, 1, 0, 0), 12),
    ((-1, 42, 1, 1, -1, 2, 1, 1, 0, 2, 0), 42),
    ((-1, 42, -1, 0, 1, 1, 1, 10, -1, 99, 0), 42),
    (
        (
            -1, 4, 1, 1, -1, 0, -1, 0, 1, 1, -1, 1,
            1, 1, 0, 0, -1, 1, 1, 0, 1, 1, -1, 0,
            1, 1, 0, 0, 1, 1, 1, 52, 1, 1, 0, 1,
            1, 1, 0, 0, 1, -1, 1, 1, -1, 1, -1, 0,
            1, 1, 1, 12, 1, 1, 0, 1, 0,
        ),
        6,
    ),
    ((1, -1, 0), None),
    ((2, 0), None),
    ((-1,), None),
    ((-1, 7, 1, 1, -1, 16, 0), None),
    ((-1, 0, 1, 1, 1, 99, 0), None),
    ((-1, 42), None),
)


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_bounded_vm_executes_programs_and_rejects_malformed_bytecode(optimization) -> None:
    compilation = compile_source(_vm_program(VM_CASES), optimization=optimization)
    assert execute_ir(compilation.ir) == 0
    if optimization is OptimizationLevel.O1:
        native = X8664Backend().generate(compilation.assembly)
        assert "__s3_builtin_i64_vector_new" in native
        assert "__s3_builtin_i64_vector_get" in native
        assert "__s3_builtin_i64_vector_set" in native


PEBBLE_CASES = (
    ("a=2; b=3; ! a+b;", 5),
    ("p=19; ! p-7;", 12),
    ("a=4; b=a+6; ! b-3;", 7),
    ("d=9; c=d-2+5; ! c;", 12),
    ("a=0-12; ! a+15;", 3),
    ("! a+1;", None),
    ("a=1; ! b;", None),
    ("a=2;", None),
    ("a=1+; ! a;", None),
    ("a=1; ! a", None),
)


def _pebble_program(cases: tuple[tuple[str, int | None], ...]) -> str:
    source = PEBBLE_SOURCE.read_text(encoding="utf-8") + "\n" + VM_SOURCE.read_text(encoding="utf-8")
    lines = ["fn main() -> i64:", "    mut failures: i64 = 0"]
    for index, (program_text, expected) in enumerate(cases):
        input_name = f"input_{index}"
        output_name = f"output_{index}"
        status_name = f"status_{index}"
        result_name = f"result_{index}"
        lines.extend(
            [
                f'    mut {input_name}: text = text_from_static("{program_text}")',
                f"    mut {output_name}: i64_vector = i64_vector_new(text_len(&{input_name}) * 8 + 8)",
                f"    mut {status_name}: trit = compile_pebble(&{input_name}, &mut {output_name})",
            ]
        )
        if expected is None:
            lines.extend(
                [
                    f"    match {status_name} <=> 0:",
                    "        -1:",
                    "            failures = failures + 1",
                    "        0:",
                    "            failures = failures",
                    "        1:",
                    "            failures = failures + 1",
                ]
            )
        else:
            lines.extend(
                [
                    f"    match {status_name} <=> -1:",
                    "        -1:",
                    "            failures = failures + 1",
                    "        0:",
                    f"            mut {result_name}: VmResult = run_vm(&{output_name})",
                    f"            failures = failures + mismatch_index({result_name}.value, {expected})",
                    "        1:",
                    "            failures = failures + 1",
                ]
            )
    lines.extend(
        [
            "    return failures",
            "fn mismatch_index(actual: i64, expected: i64) -> i64:",
            "    match actual == expected:",
            "        -1:",
            "            return 0",
            "        0:",
            "            return 1",
            "        1:",
            "            return 1",
        ]
    )
    return source + "\n" + "\n".join(lines) + "\n"


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_pebble_compiler_canary_compiles_and_runs_unseen_programs(optimization) -> None:
    source = _pebble_program(PEBBLE_CASES)
    compilation = compile_source(source, optimization=optimization)
    repeated = compile_source(source, optimization=optimization)
    assert compilation.ir == repeated.ir
    assert compilation.assembly == repeated.assembly
    assert X8664Backend().generate(compilation.assembly) == X8664Backend().generate(
        repeated.assembly
    )
    assert execute_ir(compilation.ir) == 0
    if optimization is OptimizationLevel.O1:
        native = X8664Backend().generate(compilation.assembly)
        assert "__s3_builtin_bytes_from_text" in native
        assert "__s3_builtin_i64_vector_push" in native


def test_pebble_compiler_accepts_exact_output_capacity_and_rejects_short_capacity() -> None:
    source = PEBBLE_SOURCE.read_text(encoding="utf-8")
    main = """\
fn main() -> i64:
    mut input: text = text_from_static("a=1; ! a;")
    mut required: i64 = text_len(&input) * 8 + 8
    mut exact: i64_vector = i64_vector_new(required)
    mut exact_status: trit = compile_pebble(&input, &mut exact)
    mut short: i64_vector = i64_vector_new(required - 1)
    mut short_status: trit = compile_pebble(&input, &mut short)
    match exact_status <=> -1:
        -1:
            return 1
        0:
            match short_status <=> 0:
                -1:
                    return 1
                0:
                    return 0
                1:
                    return 1
        1:
            return 1
"""
    compilation = compile_source(source + "\n" + main, optimization=OptimizationLevel.O0)
    assert execute_ir(compilation.ir) == 0


def test_multimodule_records_enums_and_calls_are_deterministic(tmp_path: Path) -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from logic import score\n"
            "from domain import Mode\n"
            "from domain import Sample\n"
            "fn main() -> i64:\n"
            "    mut item: Sample = Sample(mode=Mode.Positive, value=19)\n"
            "    return score(item)\n"
        ),
        "logic.s3": (
            "module logic\n"
            "from domain import Mode\n"
            "from domain import Sample\n"
            "export fn score(item: Sample) -> i64:\n"
            "    match item.mode:\n"
            "        Mode.Negative:\n"
            "            return 0 - item.value\n"
            "        Mode.Neutral:\n"
            "            return 0\n"
            "        Mode.Positive:\n"
            "            return item.value\n"
        ),
        "domain.s3": (
            "module domain\n"
            "export enum Mode:\n"
            "    Negative\n"
            "    Neutral\n"
            "    Positive\n"
            "export record Sample:\n"
            "    mode: Mode\n"
            "    value: i64\n"
            "export fn mode_marker() -> i64:\n"
            "    return 0\n"
        ),
    }
    forward = compile_sources(sources, OptimizationLevel.O1, entry_module="main")
    reverse = compile_sources(
        tuple(reversed(tuple(sources.items()))), OptimizationLevel.O1, entry_module="main"
    )
    assert forward.ir == reverse.ir
    assert forward.assembly == reverse.assembly
    assert X8664Backend().generate(forward.assembly) == X8664Backend().generate(reverse.assembly)
    assert execute_ir(forward.ir) == execute_ir(reverse.ir) == 19
    assert execute_assembly(forward.assembly) == execute_assembly(reverse.assembly) == 19
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        return
    gcc = shutil.which("gcc")
    if gcc is None:
        pytest.skip("gcc is unavailable for the native multi-module workload")
    assembly_path = tmp_path / "multimodule.s"
    executable_path = tmp_path / "multimodule"
    assembly_path.write_text(X8664Backend().generate(forward.assembly), encoding="utf-8")
    subprocess.run(
        [gcc, "-nostartfiles", "-no-pie", str(assembly_path), "-o", str(executable_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    native = subprocess.run(
        [str(executable_path)], check=False, capture_output=True, text=True
    )
    assert native.returncode == 0, native.stdout + native.stderr
    assert "program returned: 19" in native.stdout


def _native_workload(name: str):
    if name == "ordering":
        return _ordering_program((3, 1, 2), (1, 2, 3, 0)), True
    if name == "encoding":
        return _hex_program(bytes((0, 15, 16, 127, 128, 255))), True
    if name == "csv":
        return _csv_program("-12,0,25,-3", (10, 4)), False
    if name == "vm":
        return _vm_program((VM_CASES[0],)), False
    if name == "pebble":
        return _pebble_program(PEBBLE_CASES), False
    raise AssertionError(f"unknown workload {name}")


@pytest.mark.parametrize("name", ["ordering", "encoding", "csv", "vm", "pebble"])
@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_maturity_workload_executes_as_linux_x86_64_native(
    name, optimization, tmp_path: Path
) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("native maturity workload requires Linux x86-64")
    gcc = shutil.which("gcc")
    if gcc is None:
        pytest.skip("gcc is unavailable for the native maturity workload")
    source, multi_module = _native_workload(name)
    compilation = (
        compile_sources(source, optimization=optimization, entry_module="main")
        if multi_module
        else compile_source(source, optimization=optimization)
    )
    assert execute_ir(compilation.ir) == 0
    assembly_path = tmp_path / f"{name}-{optimization.value}.s"
    executable_path = tmp_path / f"{name}-{optimization.value}"
    assembly_path.write_text(X8664Backend().generate(compilation.assembly), encoding="utf-8")
    subprocess.run(
        [gcc, "-nostartfiles", "-no-pie", str(assembly_path), "-o", str(executable_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    native = subprocess.run(
        [str(executable_path)], check=False, capture_output=True, text=True
    )
    assert native.returncode == 0, native.stdout + native.stderr
    assert "program returned: 0" in native.stdout
