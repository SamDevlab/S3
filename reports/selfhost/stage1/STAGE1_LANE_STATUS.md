# Stage1 Lane Status

Checkpoint: 2026-08-28
Base HEAD: `d67da9ea7dc8b83b0b80adb681011717eebec616`
Last validated implementation/test HEAD: `6dc94422dee9724ab9112f6e8d29248c191c445f`
Documentation checkpoint parent: `6dc94422dee9724ab9112f6e8d29248c191c445f`
Branch: `recovery/pr268-stage1-lanes-20260828`

| Lane | Hosted Contract | Native Implementation | Focused Tests | Native Probe | Status |
| --- | --- | --- | --- | --- | --- |
| S1.1 Foundation/Bindings | PASS | PASS | PASS | PASS | PASS |
| S1.2 Typed Constants | PASS | PASS | PASS | PASS | PASS |
| S1.3 Def/Use | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.4 Calls | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.5 Terminators | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.6 Serialization | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.7 General Emitter | BLOCKED | BLOCKED | PASS for blocker regression | PASS for blocker reproduction | BLOCKED |

## Gate State

`CURRENT_FIRST_BLOCKER=S1.3_DEF_USE`

`EXACT_REPRODUCER=fn main() -> tryte: return 1 + 2; canonical self-input remains S3_STAGE1_EMITTER_BLOCKED until S1.3-S1.7 close the remaining lanes`

`RECOVERED_WAVE_B_CANDIDATE=PASS_HASH_ff047a880b871d6428e2f33198db09d9b5c416b940df8bfe4d96867031439858`

`NEXT_ALLOWED_TASK=integrate canonical def/use records consuming the S1.2 semantic value IDs`

`SELF_EMIT=NOT_RUN`

`STAGE2=NOT_RUN`

`STAGE3=NOT_RUN`

No lane is marked PASS without a corresponding contract, focused test, and
native evidence. The structured sequence remains S1.2 through S1.7, followed
by native Stage1 and only then self-emission.

## S1.2 Reconciliation

The canonical source now records each numeric literal as a typed constant
definition, with kind `3`, the existing type-code mapping, an owning function,
and a source anchor. Semantic value IDs are allocated after the parameter and
local binding IDs; the definition-table index is not exposed as a value ID and
no storage or scratch slot is used as identity. Repeated literal occurrences
remain distinct, matching the candidate's factual behavior.

The final semantic capacity is enforced after all bindings are known. For the
canonical self-input, the remaining suffix is `299..364`; excess constant
occurrences fail closed and are not reported with out-of-domain IDs. The native
probe confirms the minimal literal path, local initializer, addition, existing
type codes, deterministic repeated execution, and exact unresolved-identifier
failure. The canonical self-input still exits at the expected
`S3_STAGE1_EMITTER_BLOCKED` boundary, so S1.3 is the next allowed lane and no
general emitter capability is being claimed.
