# Stage05 command card — Codex fast path

Use this file to avoid rereading the full control package during the current paired Stage05 campaign.

This card never overrides `CURRENT.json` or `OVERRIDES.md`. If the revision changes, re-read those first.

## Current atomic task — revision 22

Latest trace supersedes the evaluator hypothesis.

Known positive control:

```text
one-argument internal call
RC=0
C emitted
A ordered
Z=3
```

Unresolved callee remains fail-closed.

Two comma/cursor defects were already repaired and must remain fixed.

Latest proven cause for the multi-argument `Z0`:

```text
Stage05 already consumes a token
-> same token falls through into legacy dispatcher
-> common-parenthesis/legacy path reprocesses it
-> parse_ok becomes 0 before evaluator error handling
```

Permanent rule now reported in the clean candidate:

```text
if current token was explicitly consumed by Stage05 in this cycle:
    skip legacy reprocessing/rejection for this same token
else:
    preserve legacy behavior exactly
```

Do not globally whitelist `(`, `)`, comma or punctuation.

Read:

```text
codex-control/STAGE05_CONSUMED_TOKEN_LEGACY_GUARD.md
```

## Build already in flight

Finish the single native Linux build already running. No new source edit or build before terminal state.

Then use the same binary for:

```text
zero_arg_internal_call.s3
internal_one_arg_call.s3
ordered_two_arg_internal_call.s3
```

Use pinned LF fixtures and hashes from `codex-control/fixtures/stage05/MANIFEST.json`.

Record existing evidence only:

```text
EXIT_CODE
Z_MASK
CALL_OPCODE
C_RECORD_PRESENT
A_RECORD_COUNT
A_VALUE_IDS_IN_SOURCE_ORDER
O_RECORD_COUNT
O_VALUE_IDS_IN_SOURCE_ORDER
R_RECORD_COUNT
PARSE_OK_FINAL
```

Stop at first unexpected result.

## Immediate routing

```text
one-arg regresses
  -> STOP: guard/shared parser regression

two-arg still Z0
  -> preserve first remaining setter; do not return to evaluator/capacity by default

zero/one/two structurally valid
  -> run stage-local strict Stage05 conformance on one-arg before arrays
```

Strict gate:

```text
strict FAIL
  -> errors[0] only

strict PASS + Z3
  -> inspect only Stage05/S3 completeness predicate
  -> do not force bit 4

strict PASS + Z7
  -> continue same-binary internal matrix:
     nested -> result reuse -> unresolved fail-closed
```

## Locked

No arrays yet.
No foreign-call edits yet.
No capacity changes.
No Stage06.
No canonical mutation.
No SELF_EMIT.
No Stage2/Stage3/T4.
