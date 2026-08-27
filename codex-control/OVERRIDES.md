# Live overrides

CONTROL_REVISION: 11

No emergency stop is active.

## Current direction

- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`; preserve/push the local Stage04 checkpoint on the next implementation commit without fabricating remote evidence.
- Stage 05 remains active under paired engineering mode.
- Automatic stage advance remains disabled.
- Read `codex-control/STAGE05_CALL_PAREN_DIFFERENTIAL.md` before the next probe.

## Latest paired update

The deeper temporary instrumentation around call close was rejected because the debug-only insertion created an indentation error. That instrumentation was then removed and the clean candidate was regenerated. This is not a semantic candidate failure.

A single clean native build is already reported in flight. Finish that exact build. Do not start another build.

The prior valid diagnostic still stands:

```text
simple helper expression -> parse_ok=-1
helper(1)                -> parse_ok=0 during parsing
failure before eval      -> YES
```

## Immediate same-binary differential

After the clean build reaches terminal state, run exactly two inputs through that same binary.

A — grouping control:

```s3
fn helper(value: i64) -> i64:
    return value

fn main() -> i64:
    return (1)
```

```text
SHA256=644ff711960765a99f981fbfc98c94bb65dd66b5c8b76f8194ec2e672d6c2b8b
```

B — internal call reproducer:

```s3
fn helper(value: i64) -> i64:
    return value

fn main() -> i64:
    return helper(1)
```

```text
SHA256=769480e71eb4ed6711aa1bc608f000ea6f2802894df9796871277a33d72b2f34
```

Record raw stdout/stderr/exit and Z mask for both. Do not add new instrumentation merely to run this differential.

## Classification

If A succeeds and B fails:

```text
CALL_SPECIFIC_PARSER_FRAME_BUG
```

Do not modify generic grouping. Inspect only postfix call-open, argument stop at call depth, right-paren call close, and call-frame restoration.

If A and B both fail:

```text
GENERIC_PAREN_CLOSE_OR_DEPTH_BUG
```

Inspect shared parenthesis/depth bookkeeping first.

If A and B both succeed:

```text
PREVIOUS_FAILURE_REMOVED_BY_CLEAN_REGENERATION_OR_STALE_DEBUG_STATE
```

Run strict Stage05 conformance on B next; do not re-instrument without a new semantic blocker.

If A fails and B succeeds:

```text
UNEXPECTED_DIFFERENTIAL
```

Stop and hand back exact raw evidence.

## Do not broaden

Until the differential is classified and the first internal call is conformant:

- no zero-arg expansion;
- no nested/multi-arg expansion;
- no foreign calls;
- no arrays;
- no capacity changes;
- no Stage06.

The valid internal-call target remains exact S1+S2+S3 with `Z 7`. `Z 31` remains forbidden until S4/S5 close.

## Authorization boundary

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2 remains unauthorized.
Stage3 remains unauthorized.
T4 remains unauthorized.
