# S3-ZK-0031 — Allocator enablement and allocator quality are different causal variables

TYPE: PERMANENT
STATUS: SUPPORTED

## Thesis

A register allocator can be non-primary as an algorithmic bottleneck while its **disabled/default-off state** is still a major cause of poor generated code.

Always separate:

```text
RA_ENABLEMENT
RA_INPUT_QUALITY
RA_ALGORITHM_QUALITY
TRUE_SPILL_BEHAVIOR
EMITTER_USE_OF_ALLOCATION
```

## P4 evidence

At the P3 anchor the allocator already had whole-function CFG liveness, interference and deterministic coloring.

P4 found:

```text
RA_PRIMARY_CAUSE=NO
```

but also:

```text
EARLIEST_LOCATION_FLEXIBILITY_LOSS=
X8664Backend.register_allocation default false
```

Making the existing allocator the native default caused a large frame-load/store reduction without an allocator rewrite.

## Consequence

Future RA investigations must not interpret:

```text
RA enabled improves code
```

as proof that:

```text
RA algorithm needs redesign.
```

The next RA-specific milestone is justified only if true spills or allocation decisions become a measured dominant residual after upstream/default-policy issues are removed.

## Connections

- [[S3-ZK-0006]] RA downstream
- [[S3-ZK-0013]] whole-function RA already exists
- [[S3-ZK-0028]] configuration information-loss boundary
- [[S3-ZK-0030]] metadata state is a different residual source

## Source

Production P4 / PR #170, reconciled in `research-lab/reconciliations/P4_20260812.md`.
