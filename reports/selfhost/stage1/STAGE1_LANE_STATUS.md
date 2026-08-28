# Stage1 Lane Status

Checkpoint: 2026-08-28
Base HEAD: `d67da9ea7dc8b83b0b80adb681011717eebec616`
Last validated implementation/test HEAD: `6842137f6cbb6c46da2f28cf9508be4e0f114bc3`
Documentation checkpoint parent: `4997e58b3b1a15e9d014c88da82e9a9c8a5b85bc`
Branch: `recovery/pr268-stage1-lanes-20260828`

| Lane | Hosted Contract | Native Implementation | Focused Tests | Native Probe | Status |
| --- | --- | --- | --- | --- | --- |
| S1.1 Foundation/Bindings | PASS | PASS | PASS | PASS | PASS |
| S1.2 Typed Constants | Candidate PASS; canonical BLOCKED | Candidate PASS; canonical BLOCKED | PASS | PASS | BLOCKED |
| S1.3 Def/Use | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.4 Calls | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.5 Terminators | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.6 Serialization | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.7 General Emitter | BLOCKED | BLOCKED | PASS for blocker regression | PASS for blocker reproduction | BLOCKED |

## Gate State

`CURRENT_FIRST_BLOCKER=S1.2_TYPED_CONSTANTS_CANONICAL_INTEGRATION`

`EXACT_REPRODUCER=fn main() -> tryte: return 1 + 2; canonical self-input still emits S3_STAGE1_EMITTER_BLOCKED`

`RECOVERED_WAVE_B_CANDIDATE=PASS_HASH_ff047a880b871d6428e2f33198db09d9b5c416b940df8bfe4d96867031439858`

`NEXT_ALLOWED_TASK=design and integrate canonical typed constant identities with definition/use links`

`SELF_EMIT=NOT_RUN`

`STAGE2=NOT_RUN`

`STAGE3=NOT_RUN`

No lane is marked PASS without a corresponding contract, focused test, and
native evidence. The structured sequence remains S1.2 through S1.7, followed
by native Stage1 and only then self-emission.

## S1.2 Reconciliation

The static audit reports `STATUS=BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP` with
32 functions, 70 parameters, 229 local declarations, 903 calls, and 1058
call arguments. The canonical source has no typed constant interning or
definition IDs, no operand/result value IDs, and no canonical serialized IR
artifact. Its numeric records preserve lexical observations rather than
semantic constant identities. The recovered expression candidate demonstrates
the required typed records, but it is not the canonical implementation and
cannot be promoted by changing the emitter contract implicitly.

The focused requirements, general-emitter, and lossless-IR tests pass after
their expectations were aligned with the current canonical source. The
canonical source check and `compileall bootstrap/s3` also pass. The canonical
self-input still emits `S3_STAGE1_EMITTER_BLOCKED`; therefore S1.2 remains
blocked and no S1.3 work is authorized.
