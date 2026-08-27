# Stage 08 — Canonical Stage1 source as candidate input

## Goal

Prove that the semantic candidate can represent the actual current `selfhost/compiler/s3c_stage1.s3` source without yet modifying that canonical compiler file.

## Required actions

1. Re-check control revision.
2. Record canonical source SHA256 and byte count.
3. Feed the canonical/current Stage1 source to the candidate semantic compiler/probe.
4. Capture the complete S3IR2 v2 stream.
5. Run strict v2 conformance.
6. Repeat enough times to prove determinism.
7. Preserve source SHA, candidate SHA, stream SHA and conformance JSON.

## Required result

```text
CANONICAL_SOURCE_AS_INPUT=PASS
CANONICAL_SOURCE_V2_CONFORMANCE=PASS
CANONICAL_SOURCE_DETERMINISM=PASS
CANONICAL_SOURCE_MUTATED=NO
S1=PASS
S2=PASS
S3=PASS
S4=PASS
S5=PASS
```

## Important

Passing this stage proves semantic representability of the real Stage1 source. It does NOT authorize changing canonical `s3c_stage1.s3` unless `canonical_stage1_mutation_authorized=true` in the live control manifest.

If authorization is false after this stage, preserve evidence and stop before Stage 09.
