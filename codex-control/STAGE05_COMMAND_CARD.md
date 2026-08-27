# Stage05 command card — Codex fast path

Use this file to avoid rereading the full control package during the current paired Stage05 campaign.

This card never overrides `CURRENT.json` or `OVERRIDES.md`. If the revision changes, re-read those first.

## Current atomic task — revision 18

The special-open guard was a real fix but not sufficient.

Current evidence:

```text
special-open legacy rejection guarded
C/A still emitted
helper()  -> Z 0
helper(1) -> Z 0
```

The remaining blocker is therefore:

```text
POST_SPECIAL_OPEN_RESIDUAL_PARSE_OK_SETTER_COMMON_TO_ZERO_AND_ONE_ARG
```

Finish only the token-trace build that is already in flight on the guarded candidate. Do not start another build or permanent repair until it terminates.

Read:

```text
codex-control/STAGE05_RESIDUAL_PARSE_TRANSITION.md
```

## What to capture

Find the FIRST `parse_ok` transition from `-1` to `0`.

Useful fields when already available in the trace:

```text
TOKEN_INDEX
TOKEN_CODE
CURRENT_KIND
PARSE_OK_BEFORE
PARSE_OK_AFTER
STAGE05_SPECIAL_OPEN
CALL_FRAME_ACTIVE
PAREN_DEPTH
OP_COUNT
ARG_COUNT
HAS_ARG
```

Do not add another instrumentation build merely to obtain every field; the first setter is the priority.

## Immediate decision

```text
flip still on synthetic special-open
  -> SPECIAL_OPEN_GUARD_COVERAGE

valid through arguments, flip on matching ')'
  -> CALL_CLOSE_COMMON_STATE

')' closes valid, flip later in same cycle
  -> POST_CALL_FALLTHROUGH_OR_FRAME_RESTORE

no parse_ok flip, final Z 0
  -> STAGE05_COMPLETENESS_OR_CONFORMANCE
```

Zero- and one-argument calls both fail, so argument-specific logic is not the default suspect.

## After one proven repair

1. regenerate a clean candidate;
2. `s3 check` once;
3. record candidate SHA256;
4. build one Linux native binary;
5. record binary SHA256;
6. run exact pinned `zero_arg_internal_call.s3` and `internal_one_arg_call.s3` on the same binary;
7. stop at first unexpected result;
8. if parser remains valid, run strict Stage05 conformance immediately;
9. consume verifier `errors[0]` only via `STAGE05_CONFORMANCE_EXPECTATIONS.md`;
10. do not rebuild between fixtures while candidate SHA is unchanged.

## First-call success target

```text
CALL opcode=14
C internal metadata=valid
A order=PASS
O order=PASS
R result=PASS when applicable
STRICT_STAGE05_CONFORMANCE=PASS
Z=7
```

A parser PASS alone is not S3 PASS. `Z 31` is not a Stage05 target.

## Do not spend time on these unless new evidence points there

- `stage05_open_kind > 0` truth experiments;
- callee recognition;
- basic C/A emission;
- SSH/toolchain requalification;
- Stage04 matrix;
- historical capacity;
- foreign calls;
- arrays;
- Stage06 or later.

## Authorization boundary

Canonical Stage1 mutation, SELF_EMIT, Stage2, Stage3, T4 and Stage06 remain unauthorized unless a newer live control revision explicitly changes them.
