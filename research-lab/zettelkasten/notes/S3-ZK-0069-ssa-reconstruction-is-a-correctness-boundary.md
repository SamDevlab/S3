# S3-ZK-0069 — SSA reconstruction is a correctness boundary

```text
TYPE=ARCHITECTURE
STATUS=SUPPORTED_BY_P12_10_AND_LITERATURE
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

After a transformation changes CFG/value structure in a way that invalidates SSA relationships, SSA repair/reconstruction is a correctness boundary. Provenance or value identity needed by later passes must be deliberately reconstructed or preserved; it cannot be recovered from incidental host-object identity.

## Origin

```text
SOURCE_DERIVED
S3_MEASURED
```

Sources:

- Rastello & Bouchez Tichadou (eds.), *SSA-based Compiler Design*, Chapter 5 on SSA reconstruction and Chapters 3/21 on construction/destruction;
- S3 P12.10: compact CFG activation was blocked by CFG eligibility plus provenance loss during SSA reconstruction until the research integration was repaired;
- Correction A: semantic instruction-site/compiler-state identity must not depend on Python `id()` / `is`.

## S3 implication

P13.2 should explicitly record which passes preserve SSA, which require reconstruction, and which semantic identities/provenance facts must survive reconstruction. Verifiers should run at the earliest point where reconstructed SSA is expected to satisfy its contract.

## Connections

```text
[[S3-ZK-0006]] --identity lost upstream cannot be fixed downstream--> [[S3-ZK-0069]]
[[S3-ZK-0009]] --information loss--> [[S3-ZK-0069]]
[[S3-ZK-0027]] --lowering information contract--> [[S3-ZK-0069]]
[[S3-ZK-0067]] --pipeline boundary--> [[S3-ZK-0069]]
```

## Falsifier

If a transformation is proven to preserve all SSA invariants and required semantic identities, no reconstruction is required for that transformation. This narrows the boundary to invalidating transformations rather than rejecting it.

## Experiment

For each active CFG/value-changing O1 pass, classify:

```text
PRESERVES_SSA
INVALIDATES_SSA
REPAIRS_SSA
REQUIRES_RECONSTRUCTION
```

Then run SSA/CFG verification immediately after the documented repair point.

## Evidence

P12.10 provides direct S3 evidence of provenance loss during SSA reconstruction. The SSA literature provides established reconstruction machinery and terminology.

## Decision

```text
SUPPORTED
```
