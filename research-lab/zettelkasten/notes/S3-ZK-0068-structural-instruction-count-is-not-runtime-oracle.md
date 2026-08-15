# S3-ZK-0068 — Structural instruction count is not a runtime oracle

```text
TYPE=PERMANENT
STATUS=SUPPORTED_BY_P12_17_AND_SYSTEMS_LITERATURE
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

A reduction in static or dynamically counted structural instructions is not sufficient evidence of a runtime improvement. Runtime remains an independent performance outcome.

## Origin

```text
SOURCE_DERIVED
S3_MEASURED
```

Source:

- Bryant & O'Hallaron, *Computer Systems: A Programmer's Perspective, 3e*: machine-level performance is affected by data movement, branches/prediction, register spilling, load/store behavior, processor execution structure and memory hierarchy; profiling is required to identify bottlenecks.

S3 evidence:

- P12.17 independently confirmed `DYNAMIC_STRUCTURAL_X86_REDUCTION=28.6103%` while compact runtime was slower by `13.2079%`, with work and timed-region equivalence passing.

## S3 implication

Future P14 research must maintain separate fields for:

```text
STATIC_STRUCTURE
DYNAMIC_STRUCTURE
RUNTIME
```

A structural mechanism may be real even when runtime benefit is absent. Promotion requires runtime evidence.

Without hardware counters, do not infer cache misses, branch mispredictions, stalls, IPC or port pressure from runtime alone.

## Connections

```text
[[S3-ZK-0021]] --information/structure metrics--> [[S3-ZK-0068]]
[[S3-ZK-0029]] --metric hierarchy--> [[S3-ZK-0068]]
[[S3-ZK-0054]] --possibility is not authorization--> [[S3-ZK-0068]]
[[S3-ZK-0067]] --causal stage attribution--> [[S3-ZK-0068]]
```

## Falsifier

This claim would be too strong only if a narrowly defined machine/model established a theorem that the counted structural metric monotonically determines runtime. No such theorem exists for the current S3 x86-64 runtime environment.

## Experiment

P14 broad rebase should record structural metrics only as diagnostic companions to calibrated runtime measurements, not as target-selection substitutes.

## Evidence

P12.17 is direct counterexample evidence inside S3. CS:APP supplies the systems-level model explaining why instruction count is only one component of performance without identifying a specific P12.17 microarchitectural cause.

## Decision

```text
SUPPORTED
```
