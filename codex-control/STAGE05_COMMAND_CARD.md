# Stage05 command card — Codex fast path

Use this file to avoid rereading the full control package during the current paired Stage05 campaign.

This card never overrides `CURRENT.json` or `OVERRIDES.md`. If the control revision changes, re-read those two files first.

## Current atomic task — revision 17

The right-parenthesis investigation is closed as the wrong first-owner hypothesis for the current fixture.

Proven root cause:

```text
callee detected
stage05_special_open active
current_kind temporarily becomes synthetic punctuation
legacy operand dispatch sees synthetic kind
legacy dispatch writes parse_ok=0
argument parsing has not started yet
```

Apply one repair only:

```text
GUARD_LEGACY_OPERAND_DISPATCH_WHEN_STAGE05_SPECIAL_OPEN_ACTIVE
```

Read `codex-control/STAGE05_SPECIAL_OPEN_GUARD_REPAIR.md` before editing.

Do not change the truth convention of `stage05_open_kind > 0`; the attempted `-1 -> 1` success-branch change was disproven by runtime behavior.

## Exact LF fixture — first proof only

Do not hand-build the probe string.

```text
codex-control/fixtures/stage05/internal_one_arg_call.s3
SHA256=769480e71eb4ed6711aa1bc608f000ea6f2802894df9796871277a33d72b2f34
```

From PowerShell, preserve native `git show` bytes:

```powershell
$ControlRef = 'origin/control/codex-stage1-semantic-v2-20260827'
$Out = Join-Path $env:TEMP 'stage05-internal-one-arg.s3'
cmd.exe /d /s /c "git show $ControlRef`:codex-control/fixtures/stage05/internal_one_arg_call.s3 > `"$Out`""
(Get-FileHash -Algorithm SHA256 $Out).Hash.ToLowerInvariant()
```

If the hash differs, do not run the fixture.

## One repair → one build

1. patch only the proven special-open guard in `tools/patch_stage1_calls_arrays_s3.py`;
2. regenerate clean candidate; temporary traces must be absent;
3. run `s3 check` once;
4. record candidate SHA256;
5. build one Linux native binary;
6. record binary SHA256;
7. run exact `internal_one_arg_call.s3`;
8. if `parse_ok` still becomes invalid, preserve only the first raw transition and stop;
9. if parsing remains valid, run strict Stage05 conformance immediately;
10. use verifier `errors[0]` only and classify through `STAGE05_CONFORMANCE_EXPECTATIONS.md`;
11. after strict conformance passes, reuse the same binary through unlocked fixtures in `STAGE05_POSTFIX_REGRESSION_MATRIX.json` until the first unexpected result.

Do not rebuild between fixtures while candidate SHA is unchanged.

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

## Do not spend time on these unless a new failure directly points there

- right-parenthesis close instrumentation;
- `stage05_open_kind > 0` truth-branch experiments;
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
