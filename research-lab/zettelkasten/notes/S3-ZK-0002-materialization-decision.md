# S3-ZK-0002 — Materialization is a decision, not a default state

```text
TYPE=BRIDGE
STATUS=SUPPORTED
CREATED=2026-08-12
```

## Atomic claim

`store logical_value -> canonical frame slot` should be modeled as an explicit **materialization decision**, not as the default representation of every cross-block scalar.

## Origin

```text
S3_CODE_INSPECTION + INFERENCE
```

P2/P3 indicate that late avoidance of individual stores/reloads has limited coverage. The stronger design question is whether memory should be introduced lazily where demanded.

## S3 implication

Candidate abstract operations:

```text
v = compute(...)
materialize(v, slot)
recover(slot) -> v2
invalidate_memory(slot)
```

These names are conceptual; production IR changes require separate evidence.

## Connections

```text
[[S3-ZK-0001]] --supports--> [[S3-ZK-0002]]
[[S3-ZK-0002]] --enables--> [[S3-ZK-0005]]
[[S3-ZK-0002]] --enables--> [[S3-ZK-0009]]
```

## Falsifier

If explicit materialization does not improve analysis clarity/opportunity coverage over a simpler current-IR policy, keep the simpler architecture.

## Experiment

Build the generic CFG prototypes so the same program can be evaluated under eager canonicalization and lazy materialization policies.
