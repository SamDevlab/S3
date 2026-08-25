# Stage1 codegen IR v2 — preparation checkpoint

Status: **candidate tooling only; native qualification pending**.

The canonical compiler source has not been modified by this preparation work.

## Closed prerequisite

- call arguments required: 736
- call argument capacity: 746
- banks: 365 + 365 + 16
- last native gate: PASS

## Current blocker

`CODEGEN_COMPLETE_IR_V2_REQUIRED_BEFORE_GENERAL_EMITTER`

The structural IR still lacks complete parameter/local identities, unified def/use/result IDs, call result linkage, and terminator condition/return linkage. General emission therefore remains fail-closed.

## Prepared candidate sequence

1. focused tooling tests
2. static storage-reuse audit
3. static fixed-array initializer audit
4. discard-event compaction candidate
5. native compaction measurement
6. packed parameter metadata candidate
7. native parameter measurement/verifier
8. native-derived local/value budget
9. local metadata candidate
10. unified def/use/result candidate
11. instruction/event in-place repack candidate
12. terminator repack candidate
13. verifier v2
14. general emitter
15. SELF_EMIT
16. Stage1 -> Stage2

Only steps through 8 are prepared by the current tooling checkpoint; steps 9+ remain unimplemented until the native evidence is available.

## Storage strategy

The working plan avoids speculative large arrays:

- four existing `ir_ast_event_records_[0..3]` banks (4 x 365) are the candidate physical IR-v2 instruction storage;
- instruction ID is the global physical slot index;
- the current code establishes `ir_instruction_count = ir_ast_event_count` after structural/control lowering, but native opcode-by-opcode one-to-one qualification is still required before those event slots can be rewritten in place;
- four existing `ir_value_records_[0..3]` banks remain the candidate unified value storage;
- call results will be linked from the instruction record rather than a new 730-entry array;
- block condition/return linkage will be packed into existing `ir_block_terminator`, retaining existing target A/B arrays.

The planned instruction record uses a bounded signed-i64 mixed-radix encoding for:

`owner + block + opcode + operandA + operandB + result + aux-ID`

Maximum planned encoded record: `6937057267692888959`, below signed-i64 maximum `9223372036854775807`.

`aux` is an ID/reference. It is deliberately **not** an arbitrary raw i64 literal or source offset.

## Literal/value issue discovered

The current structural value stream is not yet the final semantic def/use namespace. Fixed-array initializers in the compiler source contain repeated numeric values, especially zero-filled storage arrays. A static initializer audit is prepared to quantify this source burden.

No static zero count is treated as value-pool headroom. Aggregate zero-init is only a candidate representation and requires a later native Stage1 measurement proving semantic equivalence and reduced value usage.

## Home Linux command

```bash
git pull --ff-only
python3 tools/qualify_stage1_codegen_ir_v2_chain.py
```

The chain remains non-mutating. Best case:

```text
TOOLING_TESTS=PASS
STATIC_PREFLIGHT=PASS
STORAGE_REUSE=STATIC_STORAGE_AUDIT_PASS
ARRAY_INITIALIZERS=STATIC_ARRAY_INITIALIZER_AUDIT_PASS
CAPACITY_GATE=PASS
PARAMETER_GATE=PASS
NEXT_PHASE_BUDGET=READY_FOR_LOCAL_IR_V2_DESIGN
LOCAL_IR_V2_START_ALLOWED=True
CHAIN_STATUS=PASS_THROUGH_PARAMETER_CANDIDATE
CANONICAL_SOURCE_MUTATED=False
```

Do not run T4, Stage2, Stage3, benchmarks, or in-place promotion during this candidate check.

`SELF_EMIT=BLOCKED_IR_V2_INCOMPLETE`

`STAGE2=NOT_STARTED`

`STAGE3=NOT_STARTED`

`FULL_SELF_HOSTING=NO`
