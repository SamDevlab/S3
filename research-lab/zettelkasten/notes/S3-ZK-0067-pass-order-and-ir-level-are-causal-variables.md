# S3-ZK-0067 — Pass order and IR level are causal variables

```text
TYPE=PERMANENT
STATUS=SUPPORTED_BY_LITERATURE_AND_P12_14
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

Whether an optimization can act, and what it can prove, depends on where it runs in the pipeline and what information the current IR still represents. Pass order and IR level must therefore be treated as explicit causal variables in compiler experiments.

## Origin

```text
SOURCE_DERIVED
S3_MEASURED
```

Sources:

- Muchnick, *Advanced Compiler Design and Implementation*: optimization-order diagrams distinguish transformations by high-, medium-/low-level and machine/link-time representation, and discuss interactions among optimization orderings;
- Rastello & Bouchez Tichadou (eds.), *SSA-based Compiler Design*: SSA construction, reconstruction and destruction define representation boundaries around analyses and machine-code generation.

S3 evidence:

- P12.14 localized production effect loss to `STAGE_1_COMPACT_ELIGIBILITY` in `bootstrap/s3/lowering.py`;
- P12.10 previously localized a research integration blocker to CFG eligibility plus provenance loss during SSA reconstruction.

## S3 implication

P13.2 should inventory not only pass names, but also:

```text
PASS_POSITION
INPUT_IR_CONTRACT
OUTPUT_IR_CONTRACT
ANALYSES_REQUIRED
ANALYSES_INVALIDATED
INFORMATION_LOST_OR_CREATED
```

P14 should attribute a runtime mechanism to the first material amplification/information-loss stage rather than to a vague whole-optimizer label.

## Connections

```text
[[S3-ZK-0009]] --information loss--> [[S3-ZK-0067]]
[[S3-ZK-0027]] --lowering contract--> [[S3-ZK-0067]]
[[S3-ZK-0028]] --early collapse boundary--> [[S3-ZK-0067]]
[[S3-ZK-0065]] --analysis contract--> [[S3-ZK-0067]]
```

## Falsifier

A particular optimization can be position-insensitive over a proven equivalence class of IRs. Such a result narrows this claim for that transformation; it does not make pipeline placement generally irrelevant.

## Experiment

For each active O1 pass, record its actual position and inputs. For any future optimization experiment, compare structural facts at the boundary immediately before and after the first suspected causal stage.

## Evidence

Both literature and P12 provide independent support that representation stage and pass placement can determine whether later transformations are available.

## Decision

```text
SUPPORTED
```
