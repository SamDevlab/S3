# Stage 09 — Controlled canonical Stage1 integration

## Authorization gate

This stage is forbidden unless the live `CURRENT.json` contains:

```json
"canonical_stage1_mutation_authorized": true
```

If false, do not modify `selfhost/compiler/s3c_stage1.s3`.

## Goal

Integrate the already-qualified v2 semantic path into canonical Stage1 with the smallest reviewable patch.

## Required actions when authorized

1. Re-check control immediately before editing canonical source.
2. Record canonical source SHA before.
3. Apply the proven candidate semantics without redesigning S3IR2 v2.
4. Preserve fail-closed behavior.
5. Run focused tests, Stage0 check, native qualification, canonical-source conformance, JSON validation and `git diff --check`.
6. Record canonical source SHA after.
7. Commit only after all required qualification passes.

## Exit gate

```text
CANONICAL_MUTATION_AUTHORIZED=YES
CANONICAL_INTEGRATION=PASS
FOCUSED_TESTS=PASS
NATIVE_V2_CONFORMANCE=PASS
CANONICAL_SOURCE_V2_CONFORMANCE=PASS
S1=PASS
S2=PASS
S3=PASS
S4=PASS
S5=PASS
```

After this stage, semantic closure alone still does not authorize SELF_EMIT or Stage2. Proceed to General Emitter qualification first.
