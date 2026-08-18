# M1.51A Architecture Closure Report

Status: `ARCHITECTURE_CLOSED`

This report records a local, documentation-only architecture closure. The
implementation is not started and no compiler/runtime production file was
changed.

## Baseline and license

The worktree is based on the completed post-M1.50 research snapshot
`fb6820ffe82980576ecc36a8db9ad935da466f4d`. The canonical published main
baseline remains `0c4b83853f8ec091d5cf41d3f2071fc1ae06c481`.

The repository already contains Apache License 2.0 text. This campaign
reconciled the stale project metadata in `pyproject.toml` and `README.md` to
the SPDX identifier `Apache-2.0` in a separate local commit. No dual license,
GPL, AGPL, CLA, or copyright-assignment term was introduced.

## Closure answers

Records, enum payloads, static arrays, and nested fixed aggregates may own the
closed dynamic leaves `bytes`, `text`, `tryte_vector`, `i64_vector`,
`f64_vector`, `i64_map`, and `i64_set`. Collections whose elements are
arbitrary owned aggregates remain out of scope.

The ownership unit is the whole aggregate. Layout is inline fields in
declaration order with target-native alignment and deterministic tail padding.
There is no outer aggregate descriptor. The x86-64 physical descriptor for a
dynamic leaf is `base,length,capacity`, 24 bytes and 8-byte aligned; it is
private backend storage and not a language pointer.

Owned parameters use indirect internal transfer to callee-owned storage.
Owned results use a caller-provided result slot / hidden internal sret.
Moving is destructive and whole-value. Partial field moves are forbidden in
M1.51. Field borrows are lexical projections and block conflicting aggregate
move/drop. Replacement evaluates the new value, drops the old value, and then
moves the new value. Clone is deep and recursive; failed destination work is
cleaned exactly once while the source remains valid. Drop glue is static,
recursive, deterministic, and exactly once.

Owned aggregates do not cross C. M1.51 introduces no GC, refcounting, raw
pointers, general generics, or new global memory limit. O0 remains the
semantic reference and O1 must preserve it.

## M1.51/M1.52 boundary

M1.51 owns aggregate composition, layout, whole-value ownership operations,
field borrow projection, replacement transaction, recursive clone/drop, and
the internal parameter/result ABI. M1.52 owns field-sensitive path-dependent
flow: partial field moves, conditional reinitialization, join/backedge state,
edge cleanup, and exactly-once cleanup verification across all exits.

## Compatibility audit

The current code has the necessary fixed-layout and aggregate-result
precedents, but it still rejects dynamic leaves inside records, arrays, and
enums in `bootstrap/s3/semantic.py`. It has no aggregate-owned recursive drop
glue or ownership-aware aggregate IR. That is an implementation gap, not a
contradiction in the selected architecture. This campaign intentionally leaves
those files unchanged.

The implementation map is:

- Parser: `bootstrap/s3/parser.py` declaration and type parsing.
- Semantic/type system: `bootstrap/s3/semantic.py` and `bootstrap/s3/ast.py`.
- IR: `bootstrap/s3/ir.py` and `bootstrap/s3/ir_serialization.py`.
- SSA/verifier: `bootstrap/s3/ssa.py` and `bootstrap/s3/verifier.py`.
- Lowering: `bootstrap/s3/lowering.py`.
- Emulator: `bootstrap/s3/ir_emulator.py` and `bootstrap/s3/emulator.py`.
- Native x86-64: `bootstrap/s3/backends/x86_64/layout.py`, `emitter.py`, and
  `registers.py`.
- FFI: `bootstrap/s3/ffi.py` and `bootstrap/s3/python_buffer_abi.py`.
- Tests: existing `tests/test_composite_types.py`,
  `tests/test_recursive_composite_layouts.py`,
  `tests/test_enum_payload_architecture_gate.py`,
  `tests/test_fixed_array_value_boundaries.py`,
  `tests/test_aggregate_function_results.py`,
  `tests/test_m139_dynamic_buffers.py`,
  `tests/test_m140_ordered_collections.py`, and the future M1.51 focused
  matrix.

No implementation map item was modified in this campaign.

## Smart-test and validation policy

The existing impact manifest classifies `docs/**`, `spec/**`, and
`reports/**` as documentation/specification changes and `pyproject.toml` as a
tooling metadata change. T0 validation covers schema parsing, required closure
fields, license identity, diff cleanliness, and the smart-test plan. T1 is
limited to the directly relevant smart-test/tooling contract checks. T2, T3,
T4, full pytest, native certification, and benchmarks are not executed because
there is no implementation candidate.

## Open questions

There are no critical architecture questions remaining for M1.51A. Nonblocking
implementation details include the exact internal ownership op encoding and
the backend's private slot allocator; both must conform to this closure and
must be decided in the implementation campaign. The aggregate descriptor ABI
status is `CLOSED`.
