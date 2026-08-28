# Stage1 Lane Status

Checkpoint: 2026-08-28
Base HEAD: `d67da9ea7dc8b83b0b80adb681011717eebec616`
Current HEAD: `e275a4f239d029ac968f6bfb0a58244f59d81ee0`
Branch: `recovery/pr268-stage1-lanes-20260828`

| Lane | Hosted Contract | Native Implementation | Focused Tests | Native Probe | Status |
| --- | --- | --- | --- | --- | --- |
| S1.1 Foundation/Bindings | PASS | PASS | PASS | PASS | PASS |
| S1.2 Typed Constants | PASS for recovered candidate | PASS for recovered candidate | PASS | PASS | BLOCKED |
| S1.3 Def/Use | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.4 Calls | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.5 Terminators | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.6 Serialization | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.7 General Emitter | BLOCKED | BLOCKED | PASS for blocker regression | PASS for blocker reproduction | BLOCKED |

## Gate State

`CURRENT_FIRST_BLOCKER=S1.2_TYPED_CONSTANTS_CANONICAL_INTEGRATION`

`EXACT_REPRODUCER=fn main() -> tryte: return 1 + 2; canonical self-input still emits S3_STAGE1_EMITTER_BLOCKED`

`RECOVERED_WAVE_B_CANDIDATE=PASS_HASH_ff047a880b871d6428e2f33198db09d9b5c416b940df8bfe4d96867031439858`

`NEXT_ALLOWED_TASK=integrate typed constant identities into the canonical Stage1 IR`

`SELF_EMIT=NOT_RUN`

`STAGE2=NOT_RUN`

`STAGE3=NOT_RUN`

No lane is marked PASS without a corresponding contract, focused test, and
native evidence. The structured sequence remains S1.2 through S1.7, followed
by native Stage1 and only then self-emission.
