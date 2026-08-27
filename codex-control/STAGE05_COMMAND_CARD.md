# Stage05 command card — Codex fast path

Use this file to avoid rereading the full control package during the current paired Stage05 campaign.

This card never overrides `CURRENT.json` or `OVERRIDES.md`. If the revision changes, re-read those first.

## Current atomic task — revision 20

The parser/call-close lane is no longer fail-closed for the simplest internal call:

```text
RC=0
C emitted
A emitted in order
Z=3
```

That is progress, not Stage05 closure. `Z 3` means S3 is not yet claimed.

A separate multi-argument bug was then found:

```text
comma branch advances cursor twice
-> next argument skipped
```

The localized comma-cursor repair is already in a native build. Finish that build first. Do not start another build or source edit before it reaches terminal state.

Read:

```text
codex-control/STAGE05_CALL_MATRIX_BEFORE_ARRAYS.md
```

## Same-binary call matrix

After the build, run exactly:

```text
zero_arg_internal_call.s3
internal_one_arg_call.s3
ordered_two_arg_internal_call.s3
```

Record:

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

Stop immediately on the first valid-call `Z 0`, parser regression, wrong argument order, or malformed C/A/O/R shape.

## Strict gate before arrays

If zero/one/two-argument calls structurally pass, run the current stage-local strict Stage05 conformance gate on the one-argument fixture **before editing arrays or foreign calls**.

```text
strict FAIL
  -> errors[0] only

strict PASS + Z3
  -> inspect Stage05/S3 completeness predicate only
  -> find which required condition is still unset
  -> do not force bit 4

strict PASS + Z7
  -> internal one-call S3 proof ready
  -> continue internal call regression matrix on same binary
```

Report the exact verifier/command used because the frozen hosted oracle itself uses the full final completeness mask, while this campaign uses stage-local partial masks.

## Internal call order after first strict PASS

```text
zero arg
one arg
ordered two arg
nested
result reuse
unresolved callee fail-closed
```

Foreign calls and arrays stay locked until internal call semantics are stable.

## Stage05 final exit is still larger

Stage05 eventually still requires:

```text
S1=PASS
S2=PASS
S3_CALL_DATAFLOW=PASS
CALL_ARGUMENT_ORDER=PASS
INTERNAL_CALL_RESOLUTION=PASS
FOREIGN_CALL_RESOLUTION=PASS
ARRAY_INDEX_REQUIRED_SUBSET=PASS
```

Do not confuse the current internal-call slice with full Stage05 completion.

## Authorization boundary

No arrays yet.
No foreign-call edits yet.
No capacity changes.
No Stage06.
Canonical Stage1 mutation, SELF_EMIT, Stage2, Stage3 and T4 remain unauthorized.
