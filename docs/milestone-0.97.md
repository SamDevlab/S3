# Milestone 0.97 - Differential Correctness Matrix

Status:
Implementation complete for the 0.97 testing milestone.

## Objective

Milestone 0.97 establishes an internal correctness matrix for the current S3
compiler foundation. The matrix checks that observable behavior remains
equivalent across:

- hosted emulator O0;
- hosted emulator O1;
- Linux x86-64 ELF O0, when the native toolchain is available;
- Linux x86-64 ELF O1, when the native toolchain is available.

The milestone does not define a public artifact format and does not change
source syntax, IR JSON, S3 Assembly, the native ABI, the CLI, goldens, benchmark
baselines, or the public package version.

## Harness

The internal test harness lives in `tests/support/differential.py`.

It models:

- a differential case;
- a stable expectation;
- an observed result;
- the execution engine;
- the optimization level;
- stable diagnostic category and code;
- observable memory snapshots;
- tags and pass metadata for table-driven cases.

The hosted harness compiles the same source through `compile_source` in O0 and
O1, runs both artifacts in the hosted emulator, checks the expected return value
or diagnostic category/code, and then compares O0 and O1 against each other.

Diagnostic comparison deliberately uses `diagnostic_from_exception` and stable
diagnostic category/code values. It does not compare full diagnostic messages.

The harness captures only requested memory object indices. This keeps source
observable memory separate from internal implementation memory such as de-SSA
Phi buffers.

## Hosted Corpus

The hosted corpus is table-driven in
`tests/test_differential_correctness_matrix.py`.

It covers:

- TRIT minimum, zero, and maximum;
- TRYTE minimum, zero, and maximum;
- constants, addition, source subtraction, negation, comparison, tritwise
  minimum, tritwise maximum, and copy chains;
- negative, zero, and positive branches;
- diamond control flow and nested branches;
- zero-iteration, one-iteration, and multi-iteration loops;
- calls, nested calls, recursion, trit returns, tryte returns, and multiple
  parameters;
- immutable arrays, mutable arrays, different cells, dynamic indices,
  consecutive stores, load-between-store safety, and memory in loops;
- overflow, bounds, frame limit, and instruction limit diagnostics;
- SSA and de-SSA shapes including diamond joins, loop-carried values, and a
  reduced SCCP infinite-loop case.

Initialization diagnostics remain primarily covered by existing IR and Assembly
tests because the current source language requires explicit initializers for
local variables and arrays.

## Pass Matrix

The active O1 pass inventory is asserted directly in tests.

Top-level O1 function passes:

- `remove-unreachable-blocks`;
- `thread-empty-jumps`;
- `ssa-optimizations`;
- `fold-constants`;
- `eliminate-dead-pure-instructions`.

Active SSA fixpoint passes:

- `gvn`;
- `copy_propagation`;
- `dse`;
- `dce`;
- `adce`;
- `licm`;
- `sccp`;
- `strength_reduction`;
- `peephole`.

`cse` remains outside O1.

For each active SSA pass, the matrix includes a source-level differential probe
that preserves O0/O1 behavior and a structural pass probe that proves a real
transformation. Where telemetry is available, tests also verify the metric and
confirm that the metric remains zero when the pass is disabled.

LICM is validated through the complete fixpoint pipeline rather than as an
isolated single-pass run, matching the current architecture where later cleanup
passes are required for final IR verification.

## Native Coverage

The native coverage is added to
`tests/test_native_x86_64_integration.py`, the file already executed by the
`native-x86-64` CI job.

The added matrix includes 12 successful representative programs and 4 controlled
runtime-error programs. Successful cases compare hosted emulator O0, hosted
emulator O1, ELF O0, and ELF O1 against the same return value. Error cases
compare hosted emulator O0/O1 diagnostic categories and verify controlled native
stderr behavior for O0/O1.

The native tests reuse `generate_native_assembly` and `NativeToolchain`. They do
not create a parallel backend and do not use elapsed time as a gate.

On non-Linux x86-64 hosts, the native fixture continues to skip exactly as the
existing native tests do. Native enforcement remains the responsibility of the
Linux x86-64 CI job.

## Regression Found

The matrix design exposed an O1 SCCP regression for a valid source program with
`while -1`. SCCP could prune all blocks containing `RETURN`, producing S3
Assembly that violated the normative requirement that each function contains at
least one `TRET`.

The fix preserves one original `RETURN` block when SCCP pruning would otherwise
leave the function without a return instruction. The preserved block remains
unreachable, so the optimized program still executes as a non-returning loop and
fails by instruction limit rather than assembly verification.

## Validation

Focused validations used for this milestone:

- `python -m pytest tests/test_differential_harness.py tests/test_differential_correctness_matrix.py -q`;
- `python -m pytest tests/test_s3_fixpoint_pipeline.py tests/test_s3_gvn.py tests/test_s3_dead_store_elimination.py tests/test_s3_licm.py tests/test_s3_sccp.py tests/test_s3_adce.py tests/test_s3_strength_reduction.py tests/test_s3_ssa_peephole.py tests/test_s3_de_ssa.py -q`;
- `python -m pytest tests/test_native_x86_64_integration.py -q`;
- targeted `compileall` runs for changed Python files;
- `git diff --check` before commits.

Full native execution is expected in CI on Linux x86-64. On Windows, the native
integration file is collected and skipped when the required toolchain is
unavailable.

## Out of Scope

- New optimizer passes.
- Optimizer module refactoring.
- Public pass configuration.
- Modules and imports.
- Records and enums.
- Self-hosted toolchain replacement.
- Heap, garbage collection, package management, or operating-system work.
