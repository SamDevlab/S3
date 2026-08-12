# S3-ZK-0028 — Configuration can be an information-loss boundary

TYPE: PERMANENT
STATUS: SUPPORTED

## Thesis

A compiler may already contain a capable optimization mechanism while a default configuration disables it early enough that later phases observe the same symptoms as an architectural information-loss problem.

The causal boundary can therefore be a **policy/default**, not necessarily a missing algorithm.

## P4 evidence

P4 established:

```text
X8664Backend.register_allocation default false
    ↓
RA_OFF default path
    ↓
emitter frame canonicalization
```

Making the existing liveness-backed allocator the native default changed the direct frame probe:

```text
loads:  1549 -> 491
stores: 1520 -> 471
```

No allocator redesign was required.

## Consequence

When tracing information loss, inspect not only IR transformations but also:

- feature defaults;
- optimization-mode selection;
- fallbacks;
- disabled passes;
- capability gates.

A dormant capability can create an apparent representational limitation.

## Connections

- [[S3-ZK-0001]] location flexibility
- [[S3-ZK-0006]] RA downstream
- [[S3-ZK-0009]] compiler information loss
- [[S3-ZK-0013]] current whole-function RA fact
- [[S3-ZK-0027]] information-lossless lowering contract
- [[S3-ZK-0031]] allocator enablement vs allocator quality

## Source

Production P4 / PR #170, reconciled in `research-lab/reconciliations/P4_20260812.md`.
