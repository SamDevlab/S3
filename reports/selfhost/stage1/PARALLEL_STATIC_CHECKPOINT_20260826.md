# PR #268 Parallel Static Closure Checkpoint

Date: 2026-08-26

## Provenance

```text
PR=268
PR_BRANCH=feature/actual-stage1-compiler-seed-20260824
PR_HEAD=0789ad2df5f200c6b35b67d591d10e016c1a557a
PR_STATE=OPEN_DRAFT_NOT_MERGED
PARALLEL_BRANCH=parallel/pr268-static-ir-closure-20260826
CANONICAL_STAGE1_SOURCE_CHANGED_BY_PARALLEL_BRANCH=NO
NATIVE_EVIDENCE_CREATED_BY_PARALLEL_BRANCH=NO
```

The active PR remains the authority for Stage1 source. This branch contains
only static contracts, audits, tests and handoff documentation. It must not be
interpreted as Stage1 native qualification.

## Current local checkpoint supplied by the active campaign

The active local/Linux campaign reported:

```text
LINUX_SSH=OK
LINUX_ARCH=x86_64
PYTHON=3.14.4
PERSISTENT_BUILD_OR_PYTEST_PROCESSES=NONE
FOCUSED_PREVIOUS=74 passed, 3 skipped
COMPILEALL=PASS
JSON_VALIDATION=PASS
DIFF_CHECK=PASS
GENERAL_EMITTER=BLOCKED_INCOMPLETE_IR
SELF_EMIT=NOT_AUTHORIZED
STAGE2=NOT_AUTHORIZED
STAGE3=NOT_AUTHORIZED
T4=NOT_AUTHORIZED
```

A later static campaign checkpoint reported approximately 32 functions, 899
calls and 228 locals, with five emitter-facing semantic closure areas still
absent. Those measurements are preserved here as external local checkpoint
context; they are not recreated or promoted by this GitHub-only branch.

## Five semantic closure surfaces

The parallel tooling no longer requires the historical seven-lane list to stay
at a fixed cardinality. Instead it normalizes the emitter-facing relationships
into five surfaces:

```text
S1 typed value definitions
S2 instruction def/use
S3 call dataflow
S4 complete terminators
S5 canonical serialized IR
```

Prepared:

```text
tools/audit_stage1_ir_closure_surfaces.py
tests/test_stage1_ir_closure_surfaces.py
```

The historical `missing_lossless_typed_lanes` list remains provenance. Closing
individual parameter/local relationships must not make the static gate fail
merely because the historical count is no longer seven.

## Storage topology gate

Prepared:

```text
tools/audit_stage1_ir_storage_topology.py
tests/test_stage1_ir_storage_topology.py
```

The host typed IR is explicitly treated as a scale/topology oracle only. The
audit classifies storage families without calibrating Stage1 arrays from host
counts:

```text
blocks       -> REPRESENTATION_NOT_COMPARABLE until semantic equivalence is proven
instructions -> STREAM_OR_REUSE_REQUIRED when host scale exceeds bounded banks
values       -> STREAM_OR_REUSE_REQUIRED when exact materialization exceeds current value slots
locals       -> REPRESENTATION_NOT_COMPARABLE until cardinality equivalence is proven
```

A Stage1 structural block measurement may be checked against the Stage1 compact
capacity independently. A host typed-block count may not be used to enlarge the
Stage1 block banks.

## Existing parallel contracts

The branch also contains fail-closed contracts for:

- compact block capacity and reversible bank routing;
- non-colliding semantic value namespace;
- local namespace rebase away from the historical fixed `64 + local_index` rule;
- streaming semantic instruction records;
- call argument/result value linkage and ABI classification;
- complete return/jump/branch terminators;
- deterministic Stage2 serialized IR envelope;
- checkpoint/provenance reconciliation.

The aggregate entry point is:

```bash
python -m tools.audit_stage1_parallel_static_closure
```

It performs no native build, no source transform, no Stage2 creation and no T4.

## Validation status in this ChatGPT runtime

A host-only clone/test attempt was made for the parallel branch, but the runtime
could not resolve `github.com`:

```text
HOST_CLONE=NOT_RUN_DNS_UNAVAILABLE
ERROR=Could not resolve host: github.com
WORKFLOW_RUNS_FOR_LATEST_PARALLEL_COMMIT=NONE
```

This is not recorded as a test failure. No `pytest` or `compileall` PASS for the
new parallel files is claimed from this runtime.

## Promotion rules

```text
STATIC_DESIGN != NATIVE_STAGE1_EVIDENCE
HOST_IR_ORACLE != STAGE1_OUTPUT
COMPACT_BLOCK_CAPACITY_PASS != COMPLETE_TERMINATOR_IR
FIVE_SURFACE_STATIC_MODEL_PASS != GENERAL_EMITTER_PASS
GENERAL_EMITTER_BLOCKED -> SELF_EMIT_BLOCKED
SELF_EMIT_BLOCKED -> STAGE2_BLOCKED -> STAGE3_BLOCKED -> T4_BLOCKED
```

## Next native integration point

When the active Linux checkout consumes this parallel tooling, the useful host
validation sequence is:

```bash
python -m compileall -q tools tests
python -m pytest -q \
  tests/test_stage1_ir_closure_surfaces.py \
  tests/test_stage1_ir_storage_topology.py \
  tests/test_stage1_compact_block_capacity_contract.py \
  tests/test_stage1_checkpoint_consistency.py \
  tests/test_stage1_codegen_ir_v2_value_namespace.py \
  tests/test_stage1_local_namespace_rebase.py \
  tests/test_stage1_instruction_stream_contract.py \
  tests/test_stage1_call_terminator_contracts.py \
  tests/test_stage2_serialized_ir_envelope.py
python -m tools.audit_stage1_parallel_static_closure
```

Only after those static gates and the relevant native Stage1 candidate gates may
individual closure surfaces be considered for canonical promotion.
