# Stage05 command card — Codex fast path

Use this file to avoid rereading the full control package during the current paired Stage05 campaign.

This card never overrides `CURRENT.json` or `OVERRIDES.md`. If the revision changes, re-read those first.

## Current atomic task — revision 19

The residual token trace is complete.

Second proven root cause:

```text
parse_ok valid through call-open/arguments
matching ')' reached
call frame valid
arity valid
Stage05 close runs
same ')' falls through to legacy unknown-punctuation rejection
parse_ok becomes 0
```

Current repair owner:

```text
VALID_CALL_CLOSE_TOKEN_FALLS_THROUGH_LEGACY_PUNCTUATION_REJECTION
```

A build containing the localized repair is already reported in flight. Finish it. Do not start another build or source edit before terminal state.

Read:

```text
codex-control/STAGE05_CALL_CLOSE_SPECIAL_GUARD_REPAIR.md
```

## Repair semantics already frozen

Only a `RIGHT_PAREN` proven to close an active valid Stage05 call frame may bypass legacy unknown-punctuation rejection for that token cycle.

Do not globally whitelist `)`. Keep Stage05 arity/frame validation active. Preserve all non-call punctuation/grouping behavior.

## Post-build proof — same binary

Run exactly:

```text
zero_arg_internal_call.s3
internal_one_arg_call.s3
```

Use the pinned UTF-8/LF fixtures and SHA256 values from:

```text
codex-control/fixtures/stage05/MANIFEST.json
```

Record for each:

```text
EXIT_CODE=
Z_MASK=
C_RECORD_PRESENT=
A_RECORD_COUNT=
PARSE_OK_FINAL=
```

Do not rebuild between these fixtures if candidate SHA is unchanged.

## Immediate decision

```text
both valid calls -> Z 7
  -> run strict Stage05 conformance immediately on internal_one_arg_call

parser valid but Z 0
  -> stop parser edits; classify completeness/conformance

parse_ok still flips to 0
  -> preserve first remaining setter only; stop broadening
```

If strict conformance fails, use only verifier `errors[0]` and classify through `STAGE05_CONFORMANCE_EXPECTATIONS.md`.

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
- argument-count-specific parser repair;
- basic C/A emission;
- SSH/toolchain requalification;
- Stage04 matrix;
- historical capacity;
- foreign calls;
- arrays;
- Stage06 or later.

## Authorization boundary

Canonical Stage1 mutation, SELF_EMIT, Stage2, Stage3, T4 and Stage06 remain unauthorized unless a newer live control revision explicitly changes them.
