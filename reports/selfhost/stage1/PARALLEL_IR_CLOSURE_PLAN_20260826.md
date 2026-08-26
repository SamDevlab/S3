# PR #268 Parallel IR Closure Plan

Date: 2026-08-26

```text
BASE_HEAD=0789ad2df5f200c6b35b67d591d10e016c1a557a
PARALLEL_BRANCH=parallel/pr268-static-ir-closure-20260826
CANONICAL_COMPILER_CHANGED=NO
PR_268_HEAD_CHANGED_BY_THIS_BRANCH=NO
NATIVE_EVIDENCE_CREATED=NO
```

## Purpose

The active native scratch experiment is the compact block-capacity candidate.
It is intentionally not recreated or promoted on this branch. This branch only
contains work that can proceed without the Linux guest and without modifying
`selfhost/compiler/s3c_stage1.s3`.

The current scratch checkpoint reports 1,334 required structural blocks. Four
physical banks of 365 slots provide 1,460 slots, leaving 126 slots of bounded
headroom. The static contract freezes only the bank routing and reversible
record encoding; the 1,334 measurement remains external native-checkpoint input
and is not promotion authority.

## Parallel track A — compact block contract

Prepared:

```text
tools/audit_stage1_compact_block_capacity.py
tests/test_stage1_compact_block_capacity_contract.py
```

The contract covers:

- bank/slot boundaries at 364/365, 729/730, 1094/1095 and 1459;
- the current checkpoint block 1333 mapping to bank 3 slot 238;
- reversible packing of `owner_function`, `terminator_kind`, `target_a` and
  `target_b`;
- fail-closed rejection of out-of-domain fields;
- signed-i64 proof for the maximum encoded record;
- current verifier reads of owner/terminator/targets;
- explicit non-native/non-promoting status.

The maximum record under the bounded contract is:

```text
MAX_PACKED_BLOCK_RECORD=415661999
SIGNED_I64_MAX=9223372036854775807
```

Therefore numeric width is not the capacity blocker. Native qualification must
still prove that the S3 implementation and its typed arithmetic preserve the
same round-trip behavior.

## Parallel track B — typed IR closure dependency matrix

Prepared:

```text
tools/audit_stage1_ir_closure_dependencies.py
tests/test_stage1_ir_closure_dependencies.py
```

The existing semantic requirements still list seven missing lossless lanes.
They are grouped into five implementation workstreams without changing their
meaning:

```text
W1 symbol/value identity
   parameters + locals + typed constant definitions

W2 instruction def/use/order
   operand IDs + result IDs + complete instruction ordering

W3 call dataflow/ABI
   argument IDs + result destination + internal/foreign lowering contract

W4 terminator dataflow
   branch condition IDs + complete terminators + block targets

W5 canonical Stage2 serialization
   versioned deterministic IR artifact and independent parse boundary
```

Dependencies:

```text
W1 -> W2 -> W3
W1 + CURRENT_COMPACT_BLOCK_NATIVE_RESULT -> W4
W1 + W2 + W3 + W4 -> W5
```

All five workstreams may prepare schemas, audits, property tests and fail-closed
verifier rules in parallel. None may promote canonical Stage1 source without
its native/upstream gates.

## What remains serialized

The following must not be started merely because the parallel static work is
ready:

```text
CANONICAL_STAGE1_PROMOTION=WAIT_NATIVE_EVIDENCE
GENERAL_EMITTER_ENABLEMENT=WAIT_TYPED_RELATIONSHIPS
SELF_EMIT=WAIT_GENERAL_EMITTER
STAGE2_ARTIFACT=WAIT_COMPLETE_SERIALIZED_IR
STAGE3=WAIT_STAGE2
T4=WAIT_SOURCE_FREEZE
```

## Suggested execution when a repo runtime is available

```bash
python -m pytest -q \
  tests/test_stage1_compact_block_capacity_contract.py \
  tests/test_stage1_ir_closure_dependencies.py

python -m tools.audit_stage1_compact_block_capacity
python -m tools.audit_stage1_ir_closure_dependencies
```

Expected static statuses:

```text
STATIC_COMPACT_BLOCK_CAPACITY_CONTRACT_PASS
STATIC_PARALLEL_WORKSTREAM_MATRIX_PASS
```

These are host/static statuses only. They do not replace the active Linux native
scratch qualification.
