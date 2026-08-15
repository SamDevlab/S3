# S3-ZK-0075 — Semantic value identity is not incidental object identity

```text
TYPE=PERMANENT
STATUS=SUPPORTED
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

Compiler semantic identity must be represented explicitly as value/site/version identity; it must not depend on incidental host-object identity, and textual name identity alone is not sufficient to establish value identity.

## Origin

```text
SOURCE_DERIVED
S3_MEASURED_CORRECTNESS_DISCOVERY
```

### Source claim

Cooper & Torczon explicitly distinguishes value identity from name identity in redundancy elimination/value numbering: equivalence is established by semantic value relationships, not merely by the spelling of a variable name.

### S3 evidence

Correction A:

```text
f71eb2dad070a9a71fe8d9dec1dfbcdd7589b252
```

established independently that Python `id()` / `is` cannot serve as semantic instruction-site or compiler-state identity in S3.

### S3 inference

The source distinction and the S3 bug point toward an explicit identity contract:

```text
HOST_OBJECT_IDENTITY != SEMANTIC_IDENTITY
TEXTUAL_NAME_IDENTITY != VALUE_IDENTITY
```

Depending on the stage, valid identities may include explicit instruction-site IDs, SSA value versions, structural keys, symbol identities, or another documented stable representation.

## S3 implication

P13.1 should search correctness-critical compiler state for semantic comparisons that rely on:

```text
id(x)
x is y
raw textual name equality
```

and determine whether each use is semantically justified.

Do not replace one accidental identity scheme with another. The chosen identity must state its semantic scope and stability across reconstruction/copying.

## Connections

```text
Correction A --supports--> [[S3-ZK-0075]]
[[S3-ZK-0069]] --requires-stable-identity--> [[S3-ZK-0075]]
[[S3-ZK-0075]] --feeds--> P13.1
```

## Falsifier / narrowing condition

Host object identity can be valid for purely local implementation bookkeeping when object lifetime/uniqueness itself is the intended contract and no semantic meaning survives copying/reconstruction. Such uses must remain explicitly non-semantic.

## Experiment

P13.1 identity audit:

```text
IDENTITY_USE=
SEMANTIC_OR_INCIDENTAL=
STABILITY_REQUIRED_ACROSS_COPY=
STABILITY_REQUIRED_ACROSS_SSA_RECONSTRUCTION=
EXPLICIT_CONTRACT=
```

## Evidence

Cooper/Torczon source distinction plus the independently validated S3 Correction A.

## Decision

```text
SUPPORTED
```