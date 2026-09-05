# Stage1 Lane Status

Checkpoint: 2026-08-28
Base HEAD: `1ec76af89992f119865a370488593ad5c85c4c49`
Branch: `recovery/pr268-stage1-streaming-values-20260828`
Source status: uncommitted implementation candidate; no push performed.

| Lane | Hosted Contract | Native Implementation | Focused Tests | Native Probe | Status |
| --- | --- | --- | --- | --- | --- |
| S1.1 Foundation/Bindings | PASS | PASS | PASS | PASS | PASS |
| S1.2 Mechanism | PASS | PASS | PASS | PASS | PASS |
| S1.2 Canonical Streaming Enumeration | PASS hosted oracle | BLOCKED | PASS narrow | PASS narrow | BLOCKED |
| S1.3 Def/Use | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.4 Calls | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.5 Terminators | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.6 Serialization | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |
| S1.7 General Emitter | BLOCKED | BLOCKED | PASS blocker regression | PASS blocker reproduction | BLOCKED |

## Gate state

`CURRENT_FIRST_BLOCKER=S1.2_CANONICAL_STREAM_COMPLETENESS`

`REV35_FULL_RESIDENT_BANKING=REJECTED_NATIVE_FRAME`

`SEMANTIC_STORAGE_STRATEGY=STREAMING_MULTI_PASS`

`FULL_RESIDENT_VALUE_BANKS=ABSENT`

`FULL_RESIDENT_CONSTANT_BANKS=ABSENT`

`FRAME_GATE=PASS (main: 82781 logical trits; limit: 131072)`

`NATIVE_BUILD=PASS`

`SELF_EMIT=BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP`

`STAGE2=NOT_RUN`

`STAGE3=NOT_RUN`

The hosted S3IR2 oracle is complete at 38724 values, 58070 instructions,
37349 operand edges, 38408 result edges, 862 calls, and 3681 terminators for
the current source text. Its audited value order interleaves parameters,
constants, and instruction results by projected IR traversal, with local
bindings appended by source-binding traversal. The current Stage1 candidate
only streams a narrow numeric-constant observation path and cannot reproduce
that complete namespace. The current native captures contain no S3IR2 `V`
records; `S3_STAGE1_TYPED_CONSTANT` is a partial diagnostic shape only.

The canonical self-input reaches the deliberate `S3_STAGE1_EMITTER_BLOCKED`
boundary with exit code 2. No Stage2 or Stage3 claim is made. S1.3 must not
start until canonical value enumeration and the preserved instruction lanes
are closed.

`NEXT_ALLOWED_TASK=close canonical streaming value enumeration before S1.3`

`T4=NOT_RUN`

`COMMITS_CREATED=0`

`PUSH=NO`
