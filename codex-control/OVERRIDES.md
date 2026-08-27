# Live overrides

CONTROL_REVISION: 9

No emergency stop is active.

## Current direction

- Stage 01 is complete.
- Stage 02 hosted contract qualification is recorded as PASS.
- Stage 03 transition was observed; missing detailed historical evidence remains backfill debt.
- Stage 04 is accepted for transition as `PASS_REPORTED_PENDING_REMOTE_BACKFILL` from the user-supplied live Codex evidence: focused tests PASS, strict representative conformance 10/10 PASS, full native Stage04 matrix PASS, supported fixtures `Z 3`, unsupported fixtures `Z 0`, and deterministic candidate generation reported. Preserve/push `reports/selfhost/stage1/STAGE04_CHECKPOINT_20260827.md` when the next implementation commit is created; do not fabricate missing remote evidence.
- Stage 05 is now the active implementation stage.
- Paired engineering mode remains mandatory via `codex-control/PAIRING_MODE.md`.
- Read `codex-control/STAGE05_PAIRING_PLAN.md` before continuing the current call-dataflow work.
- `allow_automatic_stage_advance=false`: do not enter Stage06 without another paired control update.

## Immediate atomic task

Codex already has an instrumented Stage05 candidate/build in flight. Finish that exact diagnostic before doing anything else.

Required order:

1. confirm `/tmp/s3-stage05-debug` exists on the Linux guest;
2. record native binary SHA256 and exact candidate source SHA256;
3. run the same minimal internal-call fixture currently under diagnosis;
4. capture `parse_ok` after RPN parsing, after evaluation, and at final closeout;
5. identify the first transition where it falls to false;
6. regenerate the clean candidate immediately after reading the diagnostics;
7. emit the Stage05 `PAIRING_CHECKPOINT` from `STAGE05_PAIRING_PLAN.md`;
8. fix only that one owning slice.

Do not start another native build while the current diagnostic build/result is unresolved.

## First Stage05 semantic slice

Close one simple internal call end-to-end before broadening scope.

The call must preserve:

- CALL opcode `14`;
- ordered `O` operand edges;
- result `R` edge when applicable;
- `C` metadata with internal callee kind `1`, resolved function id, exact ASCII callee span, argument count and result count;
- ordered `A` argument edges matching the same semantic values as the CALL `O` operands;
- call result identity reusable by return/local lowering;
- deterministic record ordering and semantic IDs independent from physical scratch/pool slots.

A Stage05 candidate with S1 + S2 + S3 proven should emit:

```text
Z 7
```

`Z 31` remains forbidden until S4/S5 close. Invalid or unresolved-call fixtures may fail closed with `Z 0`.

If a full/final verifier rejects only because the candidate is not yet `Z 31`, use the stage-aware diagnostic path; do not relabel a semantic mismatch as a mask issue and do not relabel a mask-only issue as failed call semantics.

## Expansion order

Only after the first internal call passes strict Stage05 conformance:

1. zero-argument internal call;
2. ordered multiple arguments;
3. nested call;
4. call result reuse;
5. unresolved callee fail-closed;
6. foreign resolution/signature;
7. fixed-array identity/index load/store required by canonical Stage1.

Do not implement arrays while the current internal-call `parse_ok` blocker is unresolved.

## Capacity policy

Historical call-pool evidence (`736 required / 746 capacity`) remains provenance only. Measure exact pressure from the current candidate/source before changing physical capacities. `A` edges and logical semantic values are not physical pool slots.

## Paired ownership

- Codex owns candidate implementation, generators, Stage0 checks, Linux build/run, diagnostic instrumentation, raw stdout/stderr/exit status, and candidate/binary hashes.
- ChatGPT owns oracle interpretation, control-plane transitions, benchmark triage/fixtures/contracts, and selection of the next single semantic repair slice.
- Neither side may convert missing evidence from the other side into PASS.

## Required Stage05 exit gate

```text
S1=PASS
S2=PASS
S3_CALL_DATAFLOW=PASS
CALL_ARGUMENT_ORDER=PASS
INTERNAL_CALL_RESOLUTION=PASS
FOREIGN_CALL_RESOLUTION=PASS
ARRAY_INDEX_REQUIRED_SUBSET=PASS
```

S4/S5 may still be blocked. Re-read control before Stage06.

## Authorization boundary

Canonical `selfhost/compiler/s3c_stage1.s3` mutation remains unauthorized.
SELF_EMIT remains unauthorized.
Stage2 remains unauthorized.
Stage3 remains unauthorized.
T4 remains unauthorized.

If the control branch cannot be read, Codex may finish only the current atomic command. Do not create a new implementation commit, begin another stage, mutate canonical Stage1, or cross any bootstrap/promotion gate until the live revision is readable again.
