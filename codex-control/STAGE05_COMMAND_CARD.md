# Stage05 command card — Codex fast path

Use this file to avoid rereading the full control package during the current paired Stage05 campaign.

This card never overrides `CURRENT.json` or `OVERRIDES.md`. If the control revision changes, re-read those two files first.

## Current atomic task

Finish the already in-flight `current_code == 2` right-parenthesis diagnostic. Do not start another build until it reaches terminal state.

Capture only:

```text
BEFORE_CLOSE_OP_COUNT=
BEFORE_CLOSE_PAREN_DEPTH=
BEFORE_CLOSE_ARITY=
BEFORE_CLOSE_ARGUMENT_FLAG=
BEFORE_CLOSE_PARSE_OK=
AFTER_CLOSE_OP_COUNT=
AFTER_CLOSE_PAREN_DEPTH=
AFTER_CLOSE_ARITY=
AFTER_CLOSE_ARGUMENT_FLAG=
AFTER_CLOSE_PARSE_OK=
EXIT_CODE=
Z_MASK=
```

Then regenerate the candidate cleanly so all temporary diagnostics disappear.

## Immediate classification

```text
BEFORE parse_ok false
  -> ARGUMENT_STOP_OR_TOKEN_BEFORE_RIGHT_PAREN

BEFORE valid, AFTER false
  -> RIGHT_PAREN_CALL_CLOSE

BEFORE valid, AFTER valid, final Z 0
  -> POST_PARSE_FINALIZATION_OR_COMPLETENESS
```

Do not patch more than one owning condition per cycle.

## Exact LF fixtures — do not hand-build probe strings

Fixtures and SHA256 values live in:

```text
codex-control/fixtures/stage05/MANIFEST.json
```

From PowerShell, use `cmd.exe` redirection so native `git show` bytes are preserved instead of passing the blob through PowerShell text encoding. Example for the current minimal call:

```powershell
$ControlRef = 'origin/control/codex-stage1-semantic-v2-20260827'
$Out = Join-Path $env:TEMP 'stage05-internal-one-arg.s3'
cmd.exe /d /s /c "git show $ControlRef`:codex-control/fixtures/stage05/internal_one_arg_call.s3 > `"$Out`""
(Get-FileHash -Algorithm SHA256 $Out).Hash.ToLowerInvariant()
```

Expected SHA256:

```text
769480e71eb4ed6711aa1bc608f000ea6f2802894df9796871277a33d72b2f34
```

If the hash differs, do not run the fixture. Fix materialization first. The manifest contains hashes for every later unlocked fixture.

## After a proven parser repair

1. regenerate clean candidate;
2. run `s3 check` once;
3. record candidate SHA256;
4. build one native Linux binary;
5. record binary SHA256;
6. use the same binary for all allowed fixtures in `STAGE05_POSTFIX_REGRESSION_MATRIX.json` until one fails;
7. on the first failure, stop broadening and emit a paired checkpoint;
8. if the minimal internal call passes, run strict Stage05 conformance immediately before another source edit.

Do not rebuild between fixtures when the candidate source is unchanged. A fixture failure is diagnostic evidence, not a reason to rebuild the same candidate.

## Current success target

```text
valid helper(1)
PARSE_OK=valid through closeout
CALL opcode=14
C internal metadata=valid
A order=PASS
O order=PASS
R result=PASS when applicable
STRICT_STAGE05_CONFORMANCE=PASS
Z=7
```

`Z 31` is not a Stage05 target.

## Do not spend time on these unless the current failure points there

- SSH/Linux/Python/cc requalification;
- PR OPEN/DRAFT checks;
- function/block discovery;
- Stage04 operator matrix;
- historical 736/746 capacity;
- foreign calls;
- arrays;
- Stage06 or later.

## Authorization boundary

Canonical Stage1 mutation, SELF_EMIT, Stage2, Stage3, T4 and Stage06 remain unauthorized unless a newer live control revision explicitly changes them.
