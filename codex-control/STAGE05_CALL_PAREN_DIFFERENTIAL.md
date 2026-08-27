# Stage05 call-vs-grouping differential

Purpose: classify the remaining parser blocker with one already-in-flight clean native build, without adding new instrumentation or broadening Stage05.

This probe is read-only with respect to canonical Stage1 and does not authorize Stage06, SELF_EMIT, Stage2, Stage3, or T4.

## Why this differential now

The live paired diagnostic already proved:

- a simple expression in `helper` preserves `parse_ok=-1`;
- `helper(1)` reaches `parse_ok=0` during parsing, before evaluation;
- temporary deeper instrumentation was removed after it caused a debug-only indentation error;
- the clean Stage05 candidate has been regenerated and exactly one native build is already in flight.

The next useful question is therefore binary: is a closing parenthesis generally broken, or is only the postfix call frame broken?

## Exact A/B fixtures

Keep the same two-function shape so function discovery/signature state is equivalent. Change only the expression in `main`.

### A — grouping control

```s3
fn helper(value: i64) -> i64:
    return value

fn main() -> i64:
    return (1)
```

```text
SHA256=644ff711960765a99f981fbfc98c94bb65dd66b5c8b76f8194ec2e672d6c2b8b
BYTES=81
```

### B — internal call reproducer

```s3
fn helper(value: i64) -> i64:
    return value

fn main() -> i64:
    return helper(1)
```

```text
SHA256=769480e71eb4ed6711aa1bc608f000ea6f2802894df9796871277a33d72b2f34
BYTES=87
```

## Execution rule

Do not start another build. After the clean native build already running reaches terminal state, run A then B through the exact same native binary and preserve stdout/stderr/exit code for each.

Capture at minimum:

```text
GROUPING_EXIT=
GROUPING_Z_MASK=
CALL_EXIT=
CALL_Z_MASK=
```

If existing clean output exposes parser validity without adding instrumentation, record it. Do not modify the candidate merely to expose these four fields.

## Interpretation

### Case 1 — A succeeds, B fails

Expected signature:

```text
GROUPING_Z_MASK=3 or otherwise Stage04-valid
CALL_Z_MASK=0
```

Classification:

```text
CALL_SPECIFIC_PARSER_FRAME_BUG
```

Next inspection is limited to:

1. postfix call-open classification;
2. call-frame depth/state;
3. `RIGHT_PAREN` argument stop at call depth;
4. call closer consuming/restoring state exactly once.

Do not change generic grouping behavior.

### Case 2 — A and B both fail

Classification:

```text
GENERIC_PAREN_CLOSE_OR_DEPTH_BUG
```

Inspect the shared parenthesis/depth bookkeeping first. Do not patch call metadata yet.

### Case 3 — A and B both succeed

Classification:

```text
PREVIOUS_FAILURE_REMOVED_BY_CLEAN_REGENERATION_OR_STALE_DEBUG_STATE
```

Immediately run strict Stage05 conformance on B. Do not re-instrument unless conformance supplies a new concrete blocker.

### Case 4 — A fails, B succeeds

Classification:

```text
UNEXPECTED_DIFFERENTIAL
```

Stop and hand back exact raw evidence; do not speculate.

## Success target after repair

The valid internal call must eventually prove exact S1+S2+S3 semantics and emit:

```text
Z 7
```

A grouping-only fixture remains a Stage04 semantic surface and need not claim S3 merely because Stage05 is active.

## Pairing checkpoint

```text
PAIRING_CHECKPOINT_BEGIN
CONTROL_REVISION=11
ACTIVE_STAGE=05_CALLS_ARRAYS_S3
COMMAND_CLASS=CALL_VS_GROUPING_DIFFERENTIAL
CANDIDATE_SOURCE_SHA256=<64 hex>
NATIVE_BINARY_SHA256=<64 hex>
GROUPING_FIXTURE_SHA256=644ff711960765a99f981fbfc98c94bb65dd66b5c8b76f8194ec2e672d6c2b8b
GROUPING_EXIT=<int>
GROUPING_Z_MASK=<int or absent>
CALL_FIXTURE_SHA256=769480e71eb4ed6711aa1bc608f000ea6f2802894df9796871277a33d72b2f34
CALL_EXIT=<int>
CALL_Z_MASK=<int or absent>
CLASSIFICATION=<one of the four classifications above>
FIRST_REAL_BLOCKER=<single blocker>
CANONICAL_SOURCE_MUTATED=NO
SELF_EMIT_EXECUTED=NO
STAGE2_CREATED=NO
STAGE3_CREATED=NO
T4_EXECUTED=NO
PAIRING_CHECKPOINT_END
```
