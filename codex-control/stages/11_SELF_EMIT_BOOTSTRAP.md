# Stage 11 — SELF_EMIT, Stage2, Stage3, T4

This stage contains multiple independent authorization gates.

Before each action, fetch the live control branch again.

## SELF_EMIT

Requires:

```json
"self_emit_authorized": true
```

and proven S1-S5 + General Emitter PASS.

SELF_EMIT must compile the canonical Stage1 source using the canonical/current Stage1 compiler path without delegation to Stage0/host shortcuts that invalidate self-hosting evidence.

## Stage2

Requires:

```json
"stage2_authorized": true
```

and a real successful SELF_EMIT artifact.

Record exact Stage1 source/compiler/output SHAs.

## Stage3

Requires:

```json
"stage3_authorized": true
```

and a real Stage2 compiler artifact.

Compile the same canonical source and preserve exact output hashes/evidence.

## Equivalence

Compare Stage2 and Stage3 at the strongest deterministic level supported by the bootstrap contract. Do not substitute observable-output equivalence for byte/artifact equality if the latter is required by the qualification policy.

## T4

Requires:

```json
"t4_authorized": true
```

and all preceding bootstrap gates complete.

## No automatic promotion

Never infer a later authorization from an earlier PASS. The control manifest can deliberately pause between SELF_EMIT, Stage2, Stage3 and T4 so the user/ChatGPT can inspect evidence and change the route.
