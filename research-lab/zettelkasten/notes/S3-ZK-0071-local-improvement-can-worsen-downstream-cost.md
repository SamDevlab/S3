# S3-ZK-0071 — A local compiler improvement can worsen downstream cost

```text
TYPE=PERMANENT
STATUS=SUPPORTED_AS_RESEARCH_MODEL
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

Compiler stages interact: a transformation that improves one local metric can increase constraints or cost in a later stage, so end-to-end evaluation is required before declaring a performance win.

## Origin

```text
SOURCE_DERIVED
S3_MEASURED
```

### Source claim

Cooper & Torczon describes direct interactions among code-generation components. Instruction scheduling can lengthen live ranges and increase register demand; register assignment can create false dependences that constrain scheduling; renaming can remove those dependences while consuming more registers. The book emphasizes that hard backend problems interact rather than optimize independently.

### S3 inference

S3 should treat pass interactions as part of the causal model:

```text
LOCAL_METRIC_IMPROVEMENT
!=
GLOBAL_COST_IMPROVEMENT
```

For P14, when a target is localized to one stage, inspect the immediately downstream constraints before designing a transformation.

P12.17 is compatible with this model: less structural dynamic x86 did not imply faster runtime. This note does not claim which downstream interaction caused P12.17.

## S3 implication

Do not optimize:

```text
IR_COUNT
MOVE_COUNT
EDGE_COPY_COUNT
REGISTER_USE
BRANCH_COUNT
```

in isolation and then infer runtime benefit.

Use a funnel that preserves stage-local mechanism evidence and final end-to-end runtime evidence separately.

## Connections

```text
[[S3-ZK-0067]] --supports--> [[S3-ZK-0071]]
[[S3-ZK-0068]] --supports--> [[S3-ZK-0071]]
[[S3-ZK-0071]] --requires--> [[S3-ZK-0070]]
```

## Falsifier / narrowing condition

A transformation with a proven monotone relationship to the final objective under a tightly bounded model could avoid broad end-to-end uncertainty. No such general monotone relationship is established for current S3 native runtime.

## Experiment

For a future P14 mechanism, record before/after at the target stage and at least the next materially affected stage, then measure runtime.

## Evidence

Source-derived interaction model plus the P12.17 S3 result that structural dynamic reduction and runtime moved in opposite directions.

## Decision

```text
SUPPORTED_AS_RESEARCH_MODEL
```