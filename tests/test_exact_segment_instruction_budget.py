from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from pathlib import Path

import pytest

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyParameter,
    AssemblyProgram,
    AssemblyType,
)
from bootstrap.s3.backends.x86_64.backend import (
    NATIVE_MAX_INSTRUCTIONS,
    X8664Backend,
    generate_native_assembly,
)
from bootstrap.s3.backends.x86_64.diagnostics import NativeBackendError
from bootstrap.s3.backends.x86_64.emitter import X8664Emitter
from bootstrap.s3.backends.x86_64 import InstructionBudgetMode
from bootstrap.s3.backends.x86_64.instruction_budget import (
    budget_plan_diagnostics,
    plan_budget_segments,
)
from bootstrap.s3.backends.x86_64.toolchain import NativeToolchain
from bootstrap.s3.pipeline import compile_source


LOOP_AND_CALL_SOURCE = """\
fn helper(x: tryte) -> tryte:
    return x + 1

fn main() -> tryte:
    mut i: tryte = 0
    mut total: tryte = 0
    while i < 3:
        total = total + helper(i)
        i = i + 1
    return total
"""

BOUNDS_FAILURE_SOURCE = """\
fn index() -> tryte:
    return 2

fn main() -> tryte:
    values: tryte[1] = [7]
    mut i: tryte = 0
    i = i + index()
    return values[i]
"""

REPEATED_FFI_SOURCE = """\
export fn work() -> i64:
    return 2 + 3

fn main() -> i64:
    return 0
"""

REENTRANT_FFI_SOURCE = """\
foreign fn host_callback() -> i64

export fn nested() -> i64:
    return 4

export fn outer() -> i64:
    return host_callback() + 1

fn main() -> i64:
    return 0
"""

SIDE_EFFECT_BOUNDARY_SOURCE = """\
foreign fn host_effect(value: i64) -> i64

export fn run() -> i64:
    mut value: i64 = 0
    value = value + 1
    return host_effect(value) + 1

fn main() -> i64:
    return 0
"""


def _exact_native(program, *, max_instructions: int) -> str:
    return X8664Backend(
        max_instructions=max_instructions,
        instruction_budget_mode=InstructionBudgetMode.EXACT_SEGMENT,
    ).generate(program)


def _native_toolchain() -> NativeToolchain:
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        pytest.skip("exact-segment native execution requires Linux x86-64")
    return NativeToolchain.detect()


def _run_source(
    source: str,
    directory: Path,
    toolchain: NativeToolchain,
    *,
    budget_mode: InstructionBudgetMode,
    max_instructions: int,
):
    program = compile_source(source, "O0").assembly
    if budget_mode is InstructionBudgetMode.PER_INSTRUCTION:
        assembly = generate_native_assembly(
            program,
            max_instructions=max_instructions,
        )
    else:
        assembly = _exact_native(program, max_instructions=max_instructions)
    executable = toolchain.build(assembly, directory / "program")
    return toolchain.run(executable)


def test_default_mode_matches_explicit_per_instruction_output() -> None:
    program = compile_source(LOOP_AND_CALL_SOURCE, "O0").assembly

    assert X8664Backend().instruction_budget_mode is InstructionBudgetMode.PER_INSTRUCTION
    assert generate_native_assembly(program) == X8664Backend(
        instruction_budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
    ).generate(program)


def test_default_mode_matches_frozen_e07_native_assembly_bytes() -> None:
    expected = {
        "linear": (
            50_066,
            "a3de7a61c09cca2d3d8807aed3fe0f80025cb726215e69990d661c4ba8ec485d",
        ),
        "loop_call": (
            100_099,
            "252d92b5f153d707691ca3367f49ec0feee89fbfb0aa1f216a343dd4c31b8b95",
        ),
        "bounds": (
            69_723,
            "3f6932ecf7bd67c4e2f378fa9e56e97f65e978b7cd3bc612272fb153c7a87b64",
        ),
    }
    sources = {
        "linear": "fn main() -> tryte:\n    return 6\n",
        "loop_call": LOOP_AND_CALL_SOURCE,
        "bounds": BOUNDS_FAILURE_SOURCE,
    }

    for name, source in sources.items():
        assembly = generate_native_assembly(compile_source(source, "O0").assembly)
        encoded = assembly.encode("utf-8")
        assert len(encoded) == expected[name][0]
        assert hashlib.sha256(encoded).hexdigest() == expected[name][1]


def test_planner_is_block_local_and_splits_after_calls_and_control() -> None:
    program = compile_source(LOOP_AND_CALL_SOURCE, "O0").assembly

    for function in program.functions:
        plan = plan_budget_segments(function)
        assert plan.logical_instruction_count == len(function.instructions)
        for block in function.blocks:
            segments = [segment for segment in plan.segments if segment.block == block.label]
            covered = [
                index
                for segment in segments
                for index in segment.instruction_indexes
            ]
            assert covered == list(range(len(block.instructions)))
            assert all(segment.function == function.name for segment in segments)
            assert all(
                segment.logical_weight == len(segment.instruction_indexes)
                for segment in segments
            )
            for segment in segments:
                last = block.instructions[segment.last_instruction_index].opcode.value
                if segment.barrier_type == "call":
                    assert last == "TCALL"
                elif segment.barrier_type == "branch":
                    assert last in {"TBR3", "TJMP"}
                elif segment.barrier_type == "return":
                    assert last == "TRET"

    main = next(function for function in program.functions if function.name == "main")
    main_plan = plan_budget_segments(main)
    call_segments = [
        segment
        for segment in main_plan.segments
        if segment.barrier_type == "call"
    ]
    assert call_segments
    call_segment = call_segments[0]
    call_block = next(block for block in main.blocks if block.label == call_segment.block)
    assert call_block.instructions[call_segment.last_instruction_index].opcode.value == "TCALL"
    assert any(
        segment.block == call_segment.block
        and segment.first_instruction_index > call_segment.last_instruction_index
        for segment in main_plan.segments
    )

    compare_branch_pairs = []
    for segment in main_plan.segments:
        block = next(block for block in main.blocks if block.label == segment.block)
        opcodes = [
            instruction.opcode.value
            for instruction in block.instructions[
                segment.first_instruction_index : segment.last_instruction_index + 1
            ]
        ]
        compare_branch_pairs.extend(
            opcodes[index : index + 2]
            for index in range(len(opcodes) - 1)
        )
    assert ["TCMP", "TBR3"] in compare_branch_pairs


def test_plan_diagnostics_apply_the_predeclared_fast_segment_threshold() -> None:
    program = compile_source(LOOP_AND_CALL_SOURCE, "O0").assembly
    main = next(function for function in program.functions if function.name == "main")
    diagnostics = budget_plan_diagnostics(main, max_instructions=100)
    weights = [item["logical_weight"] for item in diagnostics["segments"]]

    assert diagnostics["logical_instruction_count"] == len(main.instructions)
    assert diagnostics["fast_segment_count"] == sum(weight >= 2 for weight in weights)
    assert diagnostics["call_barriers"] >= 1
    assert diagnostics["branch_barriers"] >= 1
    assert diagnostics["return_barriers"] >= 1
    assert diagnostics["scalar_sites"] == sum(weight for weight in weights if weight == 1)


def test_exact_segment_codegen_has_exact_precharge_and_scalar_slow_path() -> None:
    program = compile_source("fn main() -> tryte:\n    return 1 + 2\n", "O0").assembly
    plan = plan_budget_segments(program.functions[0])
    segment = next(segment for segment in plan.segments if segment.logical_weight >= 2)
    weight = segment.logical_weight
    limit = weight + 1

    exact = _exact_native(program, max_instructions=limit)
    assert f"cmp qword ptr [rip + __s3_instruction_count], {limit - weight}" in exact
    assert f"add qword ptr [rip + __s3_instruction_count], {weight}" in exact
    assert "__s3_budget_0_slow:" in exact
    assert "inc qword ptr [rip + __s3_instruction_count]" in exact


def test_fast_fused_compare_keeps_context_for_guarded_register_reads() -> None:
    compare = AssemblyFunction(
        "compare",
        AssemblyType.I64,
        (
            AssemblyParameter(
                0,
                AssemblyType.REFERENCE,
                AssemblyType.I64,
                reference_is_slice=True,
            ),
            AssemblyParameter(1, AssemblyType.I64),
            AssemblyParameter(2, AssemblyType.I64),
        ),
        ((3, AssemblyType.TRIT), (4, AssemblyType.I64)),
        (
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCMP, (3, 1, 2)),
                    AssemblyInstruction(
                        AssemblyOpcode.TBR3,
                        (3,),
                        labels=("negative", "neutral", "positive"),
                    ),
                ),
            ),
            AssemblyBlock(
                "negative",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (4,), immediate=-1),
                    AssemblyInstruction(AssemblyOpcode.TRET, (4,)),
                ),
            ),
            AssemblyBlock(
                "neutral",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (4,), immediate=0),
                    AssemblyInstruction(AssemblyOpcode.TRET, (4,)),
                ),
            ),
            AssemblyBlock(
                "positive",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (4,), immediate=1),
                    AssemblyInstruction(AssemblyOpcode.TRET, (4,)),
                ),
            ),
        ),
        slice_registers=(0,),
    )
    main = AssemblyFunction(
        "main",
        AssemblyType.I64,
        (),
        ((0, AssemblyType.I64),),
        (
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=0),
                    AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
                ),
            ),
        ),
    )

    emitter = X8664Emitter(
        AssemblyProgram((compare, main)),
        max_frames=100,
        max_instructions=100,
        instruction_budget_mode=InstructionBudgetMode.EXACT_SEGMENT,
    )
    exact = emitter.emit()
    failure_contexts = [site.prefix for site in emitter.failure_sites]

    assert exact.count("cmp byte ptr") >= 2
    assert any(
        "runtime error [uninitialized register] in function 'compare'" in context
        and "(block entry, TCMP)" in context
        for context in failure_contexts
    )


def test_single_segment_w_minus_one_exact_and_w_plus_one_boundaries(
    tmp_path: Path,
) -> None:
    toolchain = _native_toolchain()
    source = "fn main() -> tryte:\n    return 1 + 2\n"
    program = compile_source(source, "O0").assembly
    plan = plan_budget_segments(program.functions[0])
    assert len(plan.segments) == 1
    weight = plan.segments[0].logical_weight
    assert weight >= 2

    for limit in (weight - 1, weight, weight + 1):
        p0 = _run_source(
            source,
            tmp_path / f"p0-{limit}",
            toolchain,
            budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
            max_instructions=limit,
        )
        p2 = _run_source(
            source,
            tmp_path / f"p2-{limit}",
            toolchain,
            budget_mode=InstructionBudgetMode.EXACT_SEGMENT,
            max_instructions=limit,
        )
        assert (p2.returncode, p2.stdout, p2.stderr) == (
            p0.returncode,
            p0.stdout,
            p0.stderr,
        )
        assert (p0.returncode == 0) is (limit >= weight)


def test_zero_budget_is_rejected_in_both_modes() -> None:
    program = compile_source("fn main() -> tryte:\n    return 1\n", "O0").assembly

    with pytest.raises(NativeBackendError, match="max_instructions must be at least 1"):
        X8664Backend(max_instructions=0).generate(program)
    with pytest.raises(NativeBackendError, match="max_instructions must be at least 1"):
        X8664Backend(
            max_instructions=0,
            instruction_budget_mode=InstructionBudgetMode.EXACT_SEGMENT,
        ).generate(program)


@pytest.mark.parametrize("max_instructions", (1, 2, 3, 4, 7, 12, 20, 40, 100))
def test_loop_calls_and_failure_boundaries_match_p0(
    max_instructions: int,
    tmp_path: Path,
) -> None:
    toolchain = _native_toolchain()
    p0 = _run_source(
        LOOP_AND_CALL_SOURCE,
        tmp_path / "p0",
        toolchain,
        budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
        max_instructions=max_instructions,
    )
    p2 = _run_source(
        LOOP_AND_CALL_SOURCE,
        tmp_path / "p2",
        toolchain,
        budget_mode=InstructionBudgetMode.EXACT_SEGMENT,
        max_instructions=max_instructions,
    )

    assert (p2.returncode, p2.stdout, p2.stderr) == (
        p0.returncode,
        p0.stdout,
        p0.stderr,
    )


def test_non_budget_runtime_failure_inside_fast_path_matches_p0(tmp_path: Path) -> None:
    toolchain = _native_toolchain()
    program = compile_source(BOUNDS_FAILURE_SOURCE, "O0").assembly
    has_fast_bounds_segment = False
    for function in program.functions:
        for segment in plan_budget_segments(function).segments:
            block = next(
                block for block in function.blocks if block.label == segment.block
            )
            opcodes = [
                instruction.opcode.value
                for instruction in block.instructions[
                    segment.first_instruction_index : segment.last_instruction_index + 1
                ]
            ]
            has_fast_bounds_segment |= (
                "TLOAD" in opcodes
                and segment.logical_weight >= 2
                and segment.logical_weight <= 10_000
            )
    assert has_fast_bounds_segment
    p0 = _run_source(
        BOUNDS_FAILURE_SOURCE,
        tmp_path / "p0",
        toolchain,
        budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
        max_instructions=10_000,
    )
    p2 = _run_source(
        BOUNDS_FAILURE_SOURCE,
        tmp_path / "p2",
        toolchain,
        budget_mode=InstructionBudgetMode.EXACT_SEGMENT,
        max_instructions=10_000,
    )

    assert p0.returncode != 0
    assert "bounds" in p0.stderr.lower()
    assert (p2.returncode, p2.stdout, p2.stderr) == (
        p0.returncode,
        p0.stdout,
        p0.stderr,
    )


def test_repeated_serial_ffi_calls_preserve_process_budget_lifetime(
    tmp_path: Path,
) -> None:
    toolchain = _native_toolchain()
    program = compile_source(REPEATED_FFI_SOURCE, "O0").assembly
    work = next(function for function in program.functions if function.name == "work")
    per_call_instructions = len(work.instructions)
    limit = per_call_instructions + 1
    driver = (
        "import ctypes, sys\n"
        "library = ctypes.CDLL(sys.argv[1])\n"
        "library.work.restype = ctypes.c_int64\n"
        "print('first=' + str(library.work()), flush=True)\n"
        "library.work()\n"
    )
    outcomes = []

    for mode in (
        InstructionBudgetMode.PER_INSTRUCTION,
        InstructionBudgetMode.EXACT_SEGMENT,
    ):
        backend = X8664Backend(
            max_instructions=limit,
            instruction_budget_mode=mode,
        )
        library = toolchain.build_shared(
            backend._generate_ffi(program),
            tmp_path / f"{mode.value}.so",
        )
        outcomes.append(
            subprocess.run(
                [sys.executable, "-c", driver, str(library)],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        )

    p0, p2 = outcomes
    assert p0.returncode == p2.returncode == 1
    assert p0.stdout == p2.stdout == "first=5\n"
    assert p0.stderr == p2.stderr
    assert "instruction limit" in p0.stderr


def test_foreign_callback_reentry_observes_a_complete_call_segment(
    tmp_path: Path,
) -> None:
    toolchain = _native_toolchain()
    program = compile_source(REENTRANT_FFI_SOURCE, "O0").assembly
    dynamic_path_length = sum(
        len(function.instructions)
        for function in program.functions
        if function.name in {"outer", "nested"}
    )
    callback_source = tmp_path / "callback.c"
    callback_source.write_text(
        "typedef long (*callback_fn)(void);\n"
        "static callback_fn nested_callback;\n"
        "void set_nested_callback(callback_fn fn) { nested_callback = fn; }\n"
        "long host_callback(void) { return nested_callback(); }\n",
        encoding="ascii",
    )
    callback_object = tmp_path / "callback.o"
    subprocess.run(
        [toolchain.compiler, "-fPIC", "-c", str(callback_source), "-o", str(callback_object)],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    driver = (
        "import ctypes, sys\n"
        "lib = ctypes.CDLL(sys.argv[1])\n"
        "callback_type = ctypes.CFUNCTYPE(ctypes.c_int64)\n"
        "callback = callback_type(lib.nested)\n"
        "lib.set_nested_callback.argtypes = [callback_type]\n"
        "lib.set_nested_callback(callback)\n"
        "lib.outer.restype = ctypes.c_int64\n"
        "print('outer=' + str(lib.outer()), flush=True)\n"
    )
    outcomes = {}

    for mode in (
        InstructionBudgetMode.PER_INSTRUCTION,
        InstructionBudgetMode.EXACT_SEGMENT,
    ):
        for limit in (dynamic_path_length, dynamic_path_length - 1):
            backend = X8664Backend(
                max_instructions=limit,
                instruction_budget_mode=mode,
            )
            library = toolchain.build_shared(
                backend._generate_ffi(program),
                tmp_path / f"{mode.value}-{limit}.so",
                extra_objects=(callback_object,),
            )
            outcomes[(mode, limit)] = subprocess.run(
                [sys.executable, "-c", driver, str(library)],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )

    p0_success = outcomes[(InstructionBudgetMode.PER_INSTRUCTION, dynamic_path_length)]
    p2_success = outcomes[(InstructionBudgetMode.EXACT_SEGMENT, dynamic_path_length)]
    assert (p0_success.returncode, p0_success.stdout, p0_success.stderr) == (
        0,
        "outer=5\n",
        "",
    )
    assert (p2_success.returncode, p2_success.stdout, p2_success.stderr) == (
        p0_success.returncode,
        p0_success.stdout,
        p0_success.stderr,
    )

    p0_limit = outcomes[(InstructionBudgetMode.PER_INSTRUCTION, dynamic_path_length - 1)]
    p2_limit = outcomes[(InstructionBudgetMode.EXACT_SEGMENT, dynamic_path_length - 1)]
    assert p0_limit.returncode == p2_limit.returncode == 1
    assert (p2_limit.stdout, p2_limit.stderr) == (p0_limit.stdout, p0_limit.stderr)


def test_side_effect_boundary_before_and_after_budget_exhaustion_matches_p0(
    tmp_path: Path,
) -> None:
    toolchain = _native_toolchain()
    program = compile_source(SIDE_EFFECT_BOUNDARY_SOURCE, "O0").assembly
    function = next(function for function in program.functions if function.name == "run")
    call_indexes = [
        index
        for index, instruction in enumerate(function.instructions)
        if instruction.opcode.value == "TCALL"
    ]
    assert len(call_indexes) == 1
    call_index = call_indexes[0]
    assert call_index > 0
    callback_source = tmp_path / "side_effect.c"
    callback_source.write_text(
        "#include <unistd.h>\n"
        "long host_effect(long value) {\n"
        "    if (value == 1) write(1, \"mutated=1\\n\", 10);\n"
        "    else write(1, \"mutated=other\\n\", 14);\n"
        "    return value;\n"
        "}\n",
        encoding="ascii",
    )
    callback_object = tmp_path / "side_effect.o"
    subprocess.run(
        [toolchain.compiler, "-fPIC", "-c", str(callback_source), "-o", str(callback_object)],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    driver = (
        "import ctypes, sys\n"
        "lib = ctypes.CDLL(sys.argv[1])\n"
        "lib.run.restype = ctypes.c_int64\n"
        "lib.run()\n"
    )
    outcomes = {}

    for mode in (
        InstructionBudgetMode.PER_INSTRUCTION,
        InstructionBudgetMode.EXACT_SEGMENT,
    ):
        for limit in (call_index, call_index + 1):
            backend = X8664Backend(
                max_instructions=limit,
                instruction_budget_mode=mode,
            )
            library = toolchain.build_shared(
                backend._generate_ffi(program),
                tmp_path / f"side-effect-{mode.value}-{limit}.so",
                extra_objects=(callback_object,),
            )
            outcomes[(mode, limit)] = subprocess.run(
                [sys.executable, "-c", driver, str(library)],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )

    for limit in (call_index, call_index + 1):
        p0 = outcomes[(InstructionBudgetMode.PER_INSTRUCTION, limit)]
        p2 = outcomes[(InstructionBudgetMode.EXACT_SEGMENT, limit)]
        assert (p2.returncode, p2.stdout, p2.stderr) == (
            p0.returncode,
            p0.stdout,
            p0.stderr,
        )
        assert p0.returncode == 1
        assert (p0.stdout == "mutated=1\n") is (limit == call_index + 1)


def test_u64_limit_domain_is_accepted_by_the_planner() -> None:
    program = compile_source("fn main() -> tryte:\n    return 1\n", "O0").assembly
    diagnostics = budget_plan_diagnostics(
        program.functions[0],
        max_instructions=NATIVE_MAX_INSTRUCTIONS,
    )
    assert diagnostics["logical_instruction_count"] == len(program.functions[0].instructions)


def test_u64_maximum_budget_assembles_and_matches_p0(tmp_path: Path) -> None:
    toolchain = _native_toolchain()
    source = "fn main() -> tryte:\n    return 1 + 2\n"
    p0 = _run_source(
        source,
        tmp_path / "p0",
        toolchain,
        budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
        max_instructions=NATIVE_MAX_INSTRUCTIONS,
    )
    p2 = _run_source(
        source,
        tmp_path / "p2",
        toolchain,
        budget_mode=InstructionBudgetMode.EXACT_SEGMENT,
        max_instructions=NATIVE_MAX_INSTRUCTIONS,
    )

    assert (p0.returncode, p0.stdout, p0.stderr) == (0, "program returned: 3\n", "")
    assert (p2.returncode, p2.stdout, p2.stderr) == (
        p0.returncode,
        p0.stdout,
        p0.stderr,
    )
