# S3-ZK-0009 — Compiler optimization as preservation of future choices

```text
TYPE=ARCHITECTURE
STATUS=OPEN
CREATED=2026-08-12
```

## Atomic claim

A compiler phase can be evaluated by whether it prematurely destroys representation choices needed by later phases; for S3, premature loss of `LOCATION_FLEXIBILITY` is a candidate root-cause metric.

## Origin

```text
ABSTRACT_INTERPRETATION_BRIDGE + S3_INFERENCE
```

Abstract domains make information loss explicit. S3 can borrow that perspective without claiming Shannon-style information theory or abstract interpretation directly solves code generation.

## Example

Before phase:

```text
v may be {register, memory, rematerialize}
```

After phase:

```text
v must be {frame slot}
```

If no semantic/resource fact justified the collapse, the phase has performed premature representation collapse.

## Candidate metrics

```text
VALUES_LOCATION_FLEXIBLE_AT_SSA=
VALUES_LOCATION_FLEXIBLE_AT_ASSEMBLY_IR=
VALUES_LOCATION_FLEXIBLE_AT_RA_INPUT=
VALUES_FORCED_MEMORY_PRE_RA=
FIRST_LOSS_LAYER_HISTOGRAM=
```

## Connections

```text
[[S3-ZK-0001]] --supports--> [[S3-ZK-0009]]
[[S3-ZK-0009]] --explains--> [[S3-ZK-0006]]
[[S3-ZK-0002]] --operationalizes--> [[S3-ZK-0009]]
```

## Falsifier

If preserving location flexibility to later phases does not expose additional optimization choices or simply shifts equivalent mandatory work later, the metric is descriptive but not actionable.

## Experiment

Instrument/trace a value corpus and build a histogram of the first layer where each value becomes memory-only.
