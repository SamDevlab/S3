# S3-ZK-0013 — Current RA already sees whole-function cross-block virtual-register liveness

```text
TYPE=PERMANENT
STATUS=SUPPORTED
CREATED=2026-08-12
```

## Atomic claim

At the P3 production anchor, `analyze_allocation(function)` consumes CFG-aware liveness for the whole `AssemblyFunction`, builds an interference graph over virtual registers, and greedily colors those vregs; therefore it is incorrect to assume the current allocator is intrinsically block-local.

## Origin

```text
S3_CODE_INSPECTION
```

Observed at production anchor `a83e25c3364302227694399ebe12946f887c0ead`:

- `liveness.py` computes block `live_in/live_out` to fixed point and instruction-level liveness;
- `allocation.py` builds interference from live-before/live-after sets;
- greedy coloring orders by degree and uses call-aware register pools;
- address-taken referents are forced stack-resident;
- a missing physical color is represented as `None`.

## S3 implication

The P4 question must distinguish at least:

```text
A. full RA path
B. P3/default narrowed residence path
C. frame traffic that exists even when a vreg could be globally colored
D. true color failure / allocator spill
```

A mandatory experiment is therefore a controlled `RA OFF` vs `RA ON` comparison on the exact same generated workloads.

## Connections

```text
[[S3-ZK-0006]] --refined-by--> [[S3-ZK-0013]]
[[S3-ZK-0009]] --measured-by--> [[S3-ZK-0013]]
```

## Falsifier

If current production architecture changes after this note, re-inspect current `liveness.py`, `allocation.py`, and emitter selection before relying on it.
