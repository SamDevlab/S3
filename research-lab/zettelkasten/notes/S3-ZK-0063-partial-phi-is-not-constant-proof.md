# S3-ZK-0063 — Partial phi knowledge is not constant proof

```text
TYPE=PERMANENT
STATUS=SUPPORTED_BY_P12_14_2_AND_LITERATURE
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

An SCCP-style analysis may treat a phi result as constant only when the abstract merge over all relevant executable incoming edges proves that constant. A partially-known phi is not sufficient proof.

## Origin

```text
SOURCE_DERIVED
S3_MEASURED
```

Sources:

- Muchnick, *Advanced Compiler Design and Implementation*, SCCP discussion and executable-edge/lattice algorithm in Chapter 12;
- Rastello & Bouchez Tichadou (eds.), *SSA-based Compiler Design*, Chapter 8 on propagation using SSA;
- S3 P12.14.2: the research compiler accepted partially-known phis and this contributed to the relaxed multi-scalar instruction-limit failure until corrected in `d9af9a9353c005dde14552ae2782525000bc9e90`.

## S3 implication

P13.1 must validate the SCCP phi lattice contract directly. `UNKNOWN` or otherwise incomplete predecessor information must remain conservative until the executable-edge merge proves a stronger fact.

This is a correctness rule, not a performance optimization.

## Connections

```text
[[S3-ZK-0010]] --precision/cost discipline--> [[S3-ZK-0063]]
[[S3-ZK-0011]] --fixpoint discipline--> [[S3-ZK-0063]]
[[S3-ZK-0054]] --possibility is not proof--> [[S3-ZK-0063]]
```

## Falsifier

A formal inspection of the current S3 SCCP implementation and its abstract domain shows that a state described as partially-known cannot reach the constant lattice state unless every relevant executable incoming value justifies it, and the historical P12 failure is shown to have a different independent cause.

That would narrow this note from an implementation-correctness requirement to a historical result only.

## Experiment

Generate bounded CFGs containing:

- same-constant phis;
- conflicting constants;
- one known plus one unknown input;
- unreachable predecessor inputs;
- loop-carried phis.

Compare O0/O1 and verify the SCCP abstract state before any replacement.

## Evidence

P12.14.2 already found and repaired an S3 SCCP partially-known-phi defect. The literature supplies the general lattice/executable-edge framing; it does not itself prove the current implementation.

## Decision

```text
SUPPORTED
```
