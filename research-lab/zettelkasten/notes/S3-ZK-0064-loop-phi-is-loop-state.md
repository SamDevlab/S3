# S3-ZK-0064 — Loop phis are loop-carried state, not ignorable merge syntax

```text
TYPE=PERMANENT
STATUS=SUPPORTED_BY_P12_14_2_AND_LITERATURE
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

A loop phi represents loop-carried value state and must participate in any analysis or transformation whose safety depends on whether a value changes across iterations. Ignoring loop phis can make an invariant proof unsound.

## Origin

```text
SOURCE_DERIVED
S3_MEASURED
```

Sources:

- Rastello & Bouchez Tichadou (eds.), *SSA-based Compiler Design*: SSA construction/destruction, liveness, loop trees and induction variables;
- Muchnick, *Advanced Compiler Design and Implementation*: loop-invariant code motion and loop analysis are data-flow/control-flow dependent transformations;
- S3 P12.14.2: LICM ignored loop phis until corrected in `d9af9a9353c005dde14552ae2782525000bc9e90`.

## S3 implication

P13.1 must isolate the generic LICM fix from compact-state research code. P13.2 should make phi/loop preconditions explicit for any pass that reasons about invariance, induction or loop-carried values.

## Connections

```text
[[S3-ZK-0037]] --phi relevance refined--> [[S3-ZK-0064]]
[[S3-ZK-0027]] --preserve needed information--> [[S3-ZK-0064]]
[[S3-ZK-0063]] --phi merge soundness--> [[S3-ZK-0064]]
```

## Falsifier

A transformation can ignore a particular loop phi only if an independent proof establishes that the phi cannot influence the candidate expression or observable semantics. The existence of such bounded cases would narrow, not reject, this general rule.

## Experiment

Regression family:

- one induction phi;
- independent invariant value plus induction phi;
- multiple loop phis;
- loop-carried mutation;
- nested loops;
- zero/one/multiple iterations;
- loop exits and post-loop uses.

Record the first pass whose verifier or O0/O1 differential diverges.

## Evidence

P12.14.2 provides direct S3 evidence that ignoring loop phis was a real correctness defect. The literature provides the general SSA/loop model.

## Decision

```text
SUPPORTED
```
