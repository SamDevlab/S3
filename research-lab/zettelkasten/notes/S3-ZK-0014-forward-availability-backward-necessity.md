# S3-ZK-0014 — Materialization may need dual analyses: forward availability + backward necessity

```text
TYPE=HYPOTHESIS
STATUS=OPEN
CREATED=2026-08-12
```

## Atomic claim

Safe lazy materialization may be cleaner when separated into two complementary data-flow questions:

```text
FORWARD:
what representations/values are definitely or possibly available here?

BACKWARD:
what representation (especially canonical memory) will definitely be required downstream before it can be recreated?
```

A materialization frontier can then be selected only where downstream necessity meets upstream ability to provide the value safely.

## Origin

```text
SOURCE_DERIVED + S3_BRIDGE
```

Program-analysis literature emphasizes dual orders/fixed-point viewpoints and the distinction between approximating program properties and approximating enabling conditions for transformations. Classical PRE also separates availability/anticipation-style questions.

The exact S3 formulation is new research.

## S3 implication

Instead of a single stateful emitter rule:

```text
if cross_block: store
```

research:

```text
AVAILABLE[value, point]
NEEDED_IN_MEMORY[value, point]
```

Then derive candidate placement.

This may naturally express:

- delayed stores;
- path-specific materialization;
- avoiding a store when downstream paths never observe memory;
- preserving conservative fallback around calls/references/address-taking.

## Connections

```text
[[S3-ZK-0002]] --motivates--> [[S3-ZK-0014]]
[[S3-ZK-0005]] --may-optimize--> [[S3-ZK-0014]]
[[S3-ZK-0003]] --may-model--> [[S3-ZK-0014]]
[[S3-ZK-0009]] --motivates--> [[S3-ZK-0014]]
```

## Falsifier

If one local/forward analysis can derive the same safe placement without loss of precision or clarity, the backward necessity analysis is unnecessary complexity.

## Experiment

On tiny diamonds/loops, compute forward value availability and backward memory necessity independently, then compare the derived frontier against the exact binary placement oracle.
