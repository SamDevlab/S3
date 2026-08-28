# Stage1 Revision 35 — Semantic Value Namespace Banking

## Purpose

Resolve the structural blocker discovered after S1.2 typed-constant work:

```text
VALUE_CAPACITY=365
BINDING_VALUE_ID_RANGE=0..298
CONSTANT_VALUE_ID_RANGE=299..364
RESULT_VALUE_ID_RANGE=NONE_AVAILABLE
```

Do not begin ordinary S1.3 instruction def/use until the canonical Stage1 can represent the complete module-monotonic semantic value namespace without violating S3 array-index rules.

## Facts

1. S3 `tryte` is bounded to `[-364,364]`.
2. S3 memory objects have a maximum length of 365 because array indices are `tryte` `0..364`.
3. Therefore a single S3 array larger than 365 elements is not a valid solution.
4. The S3IR2 reference uses `MODULE_MONOTONIC_FUNCTION_REGISTER_MAP`; logical value IDs are global/module-monotonic, not reset per function.
5. The canonical Stage1 already uses banked storage elsewhere: multiple `...[365]` arrays with logical index split into `bank=id/365` and `slot=id-bank*365`.
6. The current S1.2 implementation truncates canonical constant observation when bindings+constants exceed one 365-value bank; therefore S1.2 mechanism/fixture validation is PASS, but canonical typed-value completeness is not yet proven.

## Authorized task

Create a minimal, deterministic, banked semantic-value storage layer for the canonical Stage1 while preserving global logical value IDs as `i64`.

Before mutation, run the hosted semantic IR reference against the current canonical source and record the exact required semantic value count. The hosted oracle is architecture/reference evidence only, not native PASS evidence.

Choose the minimum explicit number of 365-element banks required to represent the current canonical source, then re-run the reference after source changes. If adding banks changes the required value count, iterate until the required count is <= bank capacity and stable. Do not add arbitrary headroom without justification.

Logical mapping:

```text
logical_value_id: i64
bank = logical_value_id / 365
slot = logical_value_id - bank * 365
0 <= slot <= 364
```

Reuse the existing Stage1 banking pattern where practical. Do not create per-function value IDs because that conflicts with the current S3IR2 logical-ID policy.

## Required gates

Prove all of the following before resuming S1.3:

```text
HOSTED_REQUIRED_VALUE_COUNT=<exact>
BANK_COUNT=<exact>
BANK_CAPACITY=BANK_COUNT*365
REQUIRED_VALUES_LE_CAPACITY=PASS
ALL_CANONICAL_BINDING_VALUES_STORED=PASS
ALL_CANONICAL_TYPED_CONSTANT_VALUES_STORED=PASS
NO_TRUNCATION_OF_TYPED_VALUE_LANE=PASS
GLOBAL_IDS_MODULE_MONOTONIC=PASS
BANK_SLOT_MAPPING=PASS
NO_ID_COLLISION=PASS
DETERMINISM=PASS
FAIL_CLOSED_BEYOND_CONFIGURED_BANKS=PASS
FOCUSED_TESTS=PASS
STAGE0=PASS
COMPILEALL=PASS
NATIVE_BUILD=PASS
NATIVE_TYPED_VALUE_PROBE=PASS
```

Only after these pass may the tracker state become:

```text
S1.2_TYPED_VALUES_CANONICAL_COMPLETENESS=PASS
CURRENT_FIRST_BLOCKER=S1.3_DEF_USE
```

Then S1.3 may add instruction I/O/R records using the same global value IDs.

## Forbidden

- Do not change one array to length >365.
- Do not reset value IDs per function.
- Do not renumber S1.2 values merely to create free slots.
- Do not start call dataflow, terminators, canonical serialization, general emitter, SELF_EMIT, Stage2, Stage3, T4, or benchmark before the required gates.
- Do not weaken tests or completeness requirements.
- Do not merge PRs, force-push, rewrite history, or mutate/clean the historical dirty worktree.
- Do not shut down, reboot, suspend, or hibernate the computer.

## Evidence policy

File presence is not PASS. Hosted oracle output is not native Stage1 evidence. Missing evidence = NOT_PROVABLE or NOT_RUN. If exact required capacity cannot be established or banked storage cannot be implemented without guessing, stop with a concrete blocker.
