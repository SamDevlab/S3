# Stage05 special-open guard repair

Purpose: freeze the first proven Stage05 parser root cause from the latest paired trace and prevent further debugging of the wrong right-parenthesis branch.

This document does not authorize foreign calls, arrays, Stage06, canonical mutation, SELF_EMIT, Stage2, Stage3, or T4.

## Proven root cause

Latest Codex trace establishes:

1. a valid internal callee is detected;
2. the Stage05 transform temporarily changes `current_kind` to a synthetic punctuation kind while `stage05_special_open` is active;
3. before the argument is parsed, the legacy operand dispatch sees that synthetic kind;
4. the legacy dispatch treats it as an invalid operand kind and writes `parse_ok = 0`;
5. therefore the later call-close / `RIGHT_PAREN` path is not the first setter for the current `helper(1)` failure.

The earlier attempted change to the truth branch of `stage05_open_kind > 0` is explicitly rejected as a root-cause fix: runtime comparison truth in this S3 path is represented by `-1`, and changing it to `1` suppresses call emission.

## Current blocker

```text
SYNTHETIC_CALL_OPEN_KIND_FALLS_THROUGH_LEGACY_OPERAND_DISPATCH
```

## Single authorized repair slice

Guard only the old operand-dispatch path so the Stage05 synthetic open token is not interpreted as a normal expression operand while `stage05_special_open` is active.

Required semantic intent:

```text
if stage05_special_open is active:
    do not run the legacy current_kind operand rejection for the synthetic open marker
    preserve parse_ok
    allow Stage05 call-open handling to continue
else:
    preserve all legacy operand behavior unchanged
```

Do not broaden this into a general parser rewrite, punctuation reclassification, truth-value convention change, or call-close rewrite.

## Required repair sequence

1. patch only the owning branch in `tools/patch_stage1_calls_arrays_s3.py`;
2. regenerate a clean candidate with no debug markers;
3. run `s3 check` once;
4. record candidate SHA256;
5. build one Linux native binary;
6. record binary SHA256;
7. run exact pinned `internal_one_arg_call.s3` first;
8. if it still reaches `Z 0`, preserve the first raw parser trace and stop broadening;
9. if parser remains valid, run strict Stage05 conformance immediately;
10. use only verifier `errors[0]` for the next repair owner;
11. once strict conformance passes, reuse the same unchanged binary through unlocked same-binary regressions.

## Success boundary for this repair

The repair itself is proven when the synthetic-open path no longer flips `parse_ok` before argument parsing.

The full first-call slice still requires:

```text
valid helper(1)
CALL opcode=14
C internal metadata=valid
A order=PASS
O order=PASS
R result=PASS when applicable
STRICT_STAGE05_CONFORMANCE=PASS
Z_MASK=7
```

A parser fix alone is not permission to claim S3 complete.

## Regression constraints

The same post-fix binary must preserve normal non-call operand behavior and grouping. Do not rebuild solely between regression fixtures while the candidate hash is unchanged.
