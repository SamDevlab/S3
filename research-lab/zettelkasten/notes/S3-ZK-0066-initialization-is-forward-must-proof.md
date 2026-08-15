# S3-ZK-0066 — Definite initialization is a forward must proof

```text
TYPE=PERMANENT
STATUS=SUPPORTED_BY_LITERATURE_AND_P8_HISTORY
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

When S3 removes or suppresses an initialization check, the supporting fact must establish definite initialization on every relevant path. This is a forward must property; possible initialization is not enough.

## Origin

```text
SOURCE_DERIVED
S3_MEASURED
```

Source:

- Møller & Schwartzbach, *Static Program Analysis*, initialized-variables analysis: initialization is a property of the past, therefore forward, and requires definite information, therefore must-analysis semantics.

S3 history:

- P8/P8.3/P8-final distinguished measured check populations from path-complete necessity and retained checked fallback where proof was absent.

## S3 implication

P13 should retain fail-closed initialization semantics. Any future analysis that feeds check elimination should document predecessor merge as an intersection/definite condition or an equivalent proof rule.

This note does not authorize additional check removal.

## Connections

```text
[[S3-ZK-0034]] --initialization state--> [[S3-ZK-0066]]
[[S3-ZK-0051]] --native observer boundary--> [[S3-ZK-0066]]
[[S3-ZK-0055]] --path-complete necessity--> [[S3-ZK-0066]]
[[S3-ZK-0056]] --validated checked fallback--> [[S3-ZK-0066]]
```

## Falsifier

A different formalization may encode the same definite-path property without a powerset/intersection must lattice. That changes the representation, not the semantic requirement that every relevant path prove initialization.

## Experiment

P13 regression set should include:

- initialized on all predecessors;
- initialized on one predecessor only;
- loop initialization before first iteration;
- loop-carried initialization;
- merge after conditional initialization;
- snapshot/TMOV interactions.

## Evidence

The literature gives the general analysis classification. S3 P8 supplies bounded historical evidence that proof-vs-possibility distinction matters operationally.

## Decision

```text
SUPPORTED
```
