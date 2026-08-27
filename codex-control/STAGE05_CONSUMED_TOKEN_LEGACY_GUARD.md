# Stage05 consumed-token legacy-dispatch guard

Revision 22 consumes the latest multi-argument trace.

## Proven cause

The evaluator is not the current owner. For the failing ordered multi-argument call, `parse_ok` is already zero before evaluator-error markers can fire.

The token trace shows a token that has already been consumed by the Stage05 expression/call parser is still allowed to fall through into the legacy dispatcher. A common-parenthesis branch can then re-handle that consumed token and write `parse_ok=0`.

This generalizes the earlier special-open and call-close fixes into one ownership rule:

```text
if Stage05 consumed the current token for valid call/expression handling:
    legacy dispatcher must not consume/reject that same token again in this cycle
else:
    legacy dispatcher behavior is unchanged
```

## Required safety boundary

Do not globally weaken punctuation or parenthesis validation.

The guard is valid only when there is explicit Stage05 evidence that the current token was already consumed. Unconsumed tokens, unmatched punctuation, invalid call frames, invalid commas and all non-Stage05 paths remain fail-closed through the legacy dispatcher.

## Current atomic task

A clean candidate containing this localized consumed-token guard is already reported in a single native Linux build.

Finish that exact build before any new edit or build.

Then reuse the same binary for the exact pinned fixtures:

```text
zero_arg_internal_call.s3
internal_one_arg_call.s3
ordered_two_arg_internal_call.s3
```

Record `EXIT_CODE`, `Z_MASK`, `C`, ordered `A`, ordered `O`, `R` and final parser state where already available.

Stop at the first valid-call `Z0` or malformed call edge.

If zero/one/two argument calls all remain structurally valid, run the current stage-local strict Stage05 conformance gate on the one-argument fixture before arrays or foreign-call edits.

## Routing after build

```text
one-arg regresses
  -> guard is too broad or shared parser state regressed; stop

two-arg remains Z0
  -> preserve first remaining setter; do not reopen evaluator/capacity by default

zero/one/two structurally valid + strict FAIL
  -> consume errors[0] only

strict PASS + Z3
  -> inspect only Stage05/S3 completeness predicate; do not force bit 4

strict PASS + Z7
  -> continue internal call matrix on same binary: nested -> result reuse -> unresolved fail-closed
```

## Locked

Arrays, foreign calls, capacity changes, Stage06, canonical mutation, SELF_EMIT, Stage2, Stage3 and T4 remain unauthorized.
