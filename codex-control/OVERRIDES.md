# Live overrides

CONTROL_REVISION: 17

No emergency stop is active.

## Current direction

- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`; preserve/push the local Stage04 checkpoint on the next implementation commit without fabricating remote evidence.
- Stage 05 remains active under paired engineering mode.
- Automatic stage advance remains disabled.
- The prior right-parenthesis diagnosis is superseded by the latest token trace.
- Read `codex-control/STAGE05_SPECIAL_OPEN_GUARD_REPAIR.md` before the next source edit.
- Use `codex-control/STAGE05_COMMAND_CARD.md` as the short operational entry point after `CURRENT.json` and this file.
- Use exact UTF-8/LF fixtures under `codex-control/fixtures/stage05/` and verify hashes against `MANIFEST.json`.

## Proven root cause

Latest paired trace proves:

```text
callee detected
stage05_special_open becomes active
current_kind is temporarily rewritten to synthetic punctuation
legacy operand dispatch sees the synthetic kind
legacy dispatch writes parse_ok=0
argument parsing has not yet occurred
```

Therefore the previous blocker:

```text
VALID_INTERNAL_CALL_REJECTED_AT_OR_AROUND_RIGHT_PAREN_CALL_CLOSE
```

is replaced by:

```text
SYNTHETIC_CALL_OPEN_KIND_FALLS_THROUGH_LEGACY_OPERAND_DISPATCH
```

The `RIGHT_PAREN` close path is not the first setter for this fixture.

The attempted change of the success branch for `stage05_open_kind > 0` from `-1` to `1` is rejected. Runtime evidence showed the original `-1` branch is the successful path here; the `1` version stopped call emission.

## Single repair only

Patch only the legacy operand-dispatch ownership boundary:

```text
when stage05_special_open is active:
  do not let the synthetic call-open marker enter the normal operand rejection path
  preserve parse_ok
  continue Stage05 call-open handling

otherwise:
  preserve legacy operand behavior exactly
```

Do not rewrite call close, truth conventions, punctuation globally, or the parser architecture.

## Required post-repair fast path

1. update only `tools/patch_stage1_calls_arrays_s3.py` for the proven guard;
2. regenerate a clean candidate with no temporary trace markers;
3. `s3 check` once;
4. record candidate SHA256;
5. build one Linux native binary;
6. record binary SHA256;
7. run exact pinned `internal_one_arg_call.s3` first;
8. if valid parsing is restored, run strict Stage05 conformance immediately;
9. preserve verifier JSON and classify `errors[0]` only via `STAGE05_CONFORMANCE_EXPECTATIONS.md`;
10. fix one owner only;
11. after strict conformance passes, reuse the unchanged binary through unlocked fixtures in `STAGE05_POSTFIX_REGRESSION_MATRIX.json` until the first unexpected result.

Do not rebuild between fixtures while candidate source/hash is unchanged.

## First-call target

```text
CALL opcode=14
C_RECORD=VALID_INTERNAL
A_ORDER=PASS
O_ORDER=PASS
R_RESULT=PASS_WHEN_APPLICABLE
STRICT_STAGE05_CONFORMANCE=PASS
Z_MASK=7
```

A parser repair by itself does not close S3.

## Time-saving prohibitions

Do not re-run or revisit unless the next failure directly implicates them:

- SSH/Linux/Python/cc qualification;
- PR OPEN/DRAFT state;
- Stage04 expression matrix;
- function/block discovery;
- right-parenthesis close instrumentation;
- the `stage05_open_kind > 0` truth-branch experiment;
- historical 736/746 capacity;
- foreign calls;
- arrays;
- Stage06 or later.

## Authorization boundary

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2 remains unauthorized.
Stage3 remains unauthorized.
T4 remains unauthorized.
Stage06 remains unauthorized.
