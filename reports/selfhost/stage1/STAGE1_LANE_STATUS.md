# Stage1 Lane Status

Checkpoint: 2026-08-28
Base: `d67da9ea7dc8b83b0b80adb681011717eebec616`
Branch: `recovery/pr268-stage1-lanes-20260828`

| Lane | Status | Evidence / blocker |
| --- | --- | --- |
| S1.1 Foundation and bindings | PASS | Wave A focused tests, `compileall bootstrap/s3`, Stage0 check, and the native trivial probe passed. |
| S1.2 Typed constants and values | BLOCKED | The semantic IR audit still lacks typed constant interning and definition IDs. |
| S1.3 Instruction definition/use | NOT_RUN | The semantic IR audit still lacks operand/result/order records. |
| S1.4 Call dataflow | NOT_RUN | Full call result and argument value IDs remain unproven. |
| S1.5 Complete terminators | NOT_RUN | Branch condition and return linkage remain unproven. |
| S1.6 Canonical serialization | NOT_RUN | No canonical serialized IR artifact is yet proven. |
| S1.7 General emitter | BLOCKED | The emitter cannot be generalized while the required semantic lanes are absent. |

## Gate State

`CURRENT_FIRST_BLOCKER=S1.2_TYPED_CONSTANTS`

`SELF_EMIT=NOT_RUN`

`STAGE2=NOT_RUN`

`STAGE3=NOT_RUN`

No lane is marked PASS without a corresponding contract, focused test, and
native evidence. The structured sequence remains S1.2 through S1.7, followed
by native Stage1 and only then self-emission.
