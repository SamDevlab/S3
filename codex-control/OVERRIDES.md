# Live overrides

CONTROL_REVISION: 34

## AUTONOMOUS OVERNIGHT — GATED STAGE1 → STAGE2 → STAGE3

Revision 34 authorizes one autonomous overnight campaign governed by:

```text
codex-control/OVERNIGHT_REV34_STAGE1_STAGE2_STAGE3.md
```

The original dirty worktree is preserved evidence and remains immutable:

```text
C:\Users\samue\Downloads\S3\S3-actual-stage1-compiler-seed-20260824
```

The clean recovery worktree is:

```text
C:\Users\samue\Downloads\S3\S3-PR268-Clean-Rev32
```

The recovery package is:

```text
C:\Users\samue\Downloads\S3\S3-PR268-Recovery-Rev31-20260827-214412
```

Base HEAD:

```text
d67da9ea7dc8b83b0b80adb681011717eebec616
```

## Mandatory first gate

Finish the revision-33 provenance graph before applying any preserved source.

File presence is not PASS evidence. Exact artifact-linked validation is required to carry historical PASS forward. Missing linkage = NOT_PROVABLE.

## Autonomous route after provenance gate

If and only if provenance establishes a safe causal reapplication plan:

```text
minimal Stage1 reapplication waves
→ smallest validation after each wave
→ narrow repairs only
→ Stage1 closure
→ SELF_EMIT
→ real Stage2
→ Stage2 builds real Stage3
→ Stage2↔Stage3 equality/determinism gate
→ correctness test matrix
→ benchmark last
→ final report
→ Windows shutdown after 60s
```

## Stage1 semantic gate

Authoritative protocol remains S3IR2 v2.

Completeness lanes:

```text
S1 typed values = 1
S2 instruction def/use = 2
S3 call dataflow = 4
S4 complete terminators = 8
S5 canonical serialization = 16
FULL = Z31
```

Do not call hosted oracle output native Stage1 evidence.

## Git authorization

A dedicated overnight branch from exact `d67da9e` is allowed, suggested:

```text
recovery/pr268-overnight-stage123-20260827
```

Small commits are allowed only after coherent validated gates/repair slices.
Normal non-force push of that dedicated branch is allowed after at least one validated checkpoint.

Forbidden:

```text
PR merge
force push
history rewrite
destructive cleanup of dirty evidence worktree
reset/restore/clean of dirty evidence worktree
```

## Repair policy

On failure:

1. capture exact command/output/exit code/hash;
2. identify first concrete failure;
3. make the narrowest attributable repair;
4. rerun the smallest validation;
5. rerun the gate;
6. do not broaden scope while blocker remains.

If the blocker is not safely attributable or requires guessing/broad unrelated changes, stop forward progress.

## Stage2 / Stage3 rules

Stage2 may only come from real SELF_EMIT after Stage1 closure.

Stage3 may only be compiled by the resulting real Stage2 compiler.

Never create Stage2/Stage3 through file copy/rename.

Stage2↔Stage3 PASS requires the project's existing equality/determinism contract. Do not invent a comparison rule during the campaign.

## Tests and benchmark

Correctness tests follow self-hosting closure, except focused tests used to validate narrow repairs.

Benchmark is LAST and only after self-hosting + correctness gates.

No performance improvement/regression claim without a comparable baseline under the same harness/environment.

## Shutdown

After either:

- successful completion through the maximum authorized gate, or
- a terminal blocker documented with exact evidence,

write and flush the final report first. Ensure no build/test/git/file-write process remains active. Then execute:

```text
shutdown.exe /s /t 60 /c "S3 overnight campaign finished; final report saved"
```

If shutdown is rejected/unavailable, record the exact error and do not escalate privileges.

## Evidence policy

```text
missing evidence = NOT_PROVABLE / NOT_RUN
failure without attribution = FAILED / NOT_ATTRIBUTED
PASS = concrete evidence only
```

Never fabricate progress.
