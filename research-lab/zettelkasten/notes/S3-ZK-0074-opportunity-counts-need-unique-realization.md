# S3-ZK-0074 — Opportunity counts need unique realizable effects

```text
TYPE=BRIDGE
STATUS=SUPPORTED_AS_RESEARCH_REQUIREMENT
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

Counting analysis facts, dependences, events, or candidate proofs does not establish an equal number of realizable optimization savings; opportunity accounting must map evidence to unique physical/semantic effects and avoid double counting.

## Origin

```text
SOURCE_DERIVED
S3_MEASURED
```

### Source claim

Allen & Kennedy gives a memory-optimization example in which several dependence edges point to the same load elimination. Treating every edge as a separate saved memory reference overcounts the actual opportunity, so the dependence graph must be pruned or otherwise interpreted with realization semantics.

### S3 inference

This generalizes a discipline already learned in P9/P10:

```text
OBSERVED_EVENT_COUNT
!=
PROVEN_AVOIDABLE_EVENT_COUNT
!=
UNIQUE_REALIZABLE_SAVING
```

A compiler census is descriptive until each candidate maps to a transformation site with provenance, legality, and a unique predicted effect.

## S3 implication

Future P14 causal ledgers should include, where applicable:

```text
RAW_EVIDENCE_COUNT=
UNIQUE_SEMANTIC_SITES=
UNIQUE_PHYSICAL_EFFECTS=
OVERLAP_CLASS=
PROVABLY_AVOIDABLE=
```

Do not sum mutually overlapping savings as if they were independent.

This rule also reinforces the existing restriction against labeling frame traffic as spill without allocator provenance.

## Connections

```text
[[S3-ZK-0057]] --supports--> [[S3-ZK-0074]]
[[S3-ZK-0060]] --supports--> [[S3-ZK-0074]]
[[S3-ZK-0061]] --supports--> [[S3-ZK-0074]]
[[S3-ZK-0074]] --governs--> P14 causal census
```

## Falsifier / narrowing condition

If a counted evidence item is proven to correspond bijectively to one independent physical saving, raw count and realizable count may coincide for that bounded class. The bijection must be demonstrated.

## Experiment

For the next performance census, explicitly reconcile raw candidate events to unique transformation sites and predicted effects before estimating a theoretical maximum improvement.

## Evidence

Allen/Kennedy source example plus S3 P9/P10 negative-result history where hot/event populations did not imply avoidable opportunities.

## Decision

```text
SUPPORTED_AS_RESEARCH_REQUIREMENT
```