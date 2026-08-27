# Live overrides

CONTROL_REVISION: 19

No emergency stop is active.

## Current direction

- Stage 04 remains accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL`.
- Stage 05 remains active under paired engineering mode.
- Automatic stage advance remains disabled.
- Preserve the previously proven `stage05_special_open` legacy-dispatch guard.
- The residual token trace is now complete and supersedes the generic revision-18 blocker.
- Read `codex-control/STAGE05_CALL_CLOSE_SPECIAL_GUARD_REPAIR.md` before any later source edit.
- A native build containing the localized call-close guard is already reported in flight. Finish that exact build before any new build or repair.

## Proven second root cause

Latest trace proves:

```text
parse_ok stays -1 through call-open and argument handling
matching ')' is reached
call frame is valid
computed arity is valid
Stage05 call-close logic runs
same ')' still reaches legacy unknown-punctuation rejection
legacy path writes parse_ok=0
```

This occurs for zero- and one-argument calls, so argument-count-specific parsing is not the owner.

Current blocker:

```text
VALID_CALL_CLOSE_TOKEN_FALLS_THROUGH_LEGACY_PUNCTUATION_REJECTION
```

## Single repair owner

Only a `RIGHT_PAREN` proven to close an active valid Stage05 call frame may be marked special for that token cycle so legacy unknown-punctuation rejection does not see it.

Required semantics:

```text
valid Stage05 call-close ')':
  keep Stage05 arity/frame validation active
  close the call normally
  skip only legacy rejection of that same token
  preserve parse_ok unless Stage05 validation itself fails

all other ')'/punctuation:
  preserve existing legacy behavior exactly
```

Do not globally whitelist `)`. Do not weaken unmatched/grouping validation. Do not revisit `stage05_open_kind > 0` truth semantics.

## Current atomic task

Finish the already-running native build containing this localized call-close guard.

Then, using the same produced binary:

1. run exact pinned `zero_arg_internal_call.s3`;
2. run exact pinned `internal_one_arg_call.s3`;
3. record exit code and final `Z` for both;
4. preserve `C/A` records and parser state evidence;
5. if either valid call still reaches `Z 0`, stop broadening and preserve the first remaining failure;
6. if both clear to Stage05 mask `Z 7`, run strict Stage05 conformance immediately on the one-arg fixture;
7. preserve verifier JSON and use only `errors[0]` for any next repair.

Do not rebuild between the zero- and one-argument fixtures while the candidate hash is unchanged.

## First-call target

```text
CALL opcode=14
C_INTERNAL=VALID
A_ORDER=PASS
O_ORDER=PASS
R_RESULT=PASS_WHEN_APPLICABLE
STRICT_STAGE05_CONFORMANCE=PASS
Z_MASK=7
```

`Z 31` remains invalid as a Stage05 target.

## Do not reopen

Unless new evidence directly contradicts it, do not revisit:

- special-open first-setter diagnosis;
- `stage05_open_kind > 0` truth experiment;
- callee recognition;
- argument-count-specific parser repair;
- basic `C/A` structural emission;
- SSH/Linux/Python/cc qualification;
- Stage04 matrix;
- arrays;
- foreign calls;
- Stage06 or later.

## Authorization boundary

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2 remains unauthorized.
Stage3 remains unauthorized.
T4 remains unauthorized.
Stage06 remains unauthorized.
