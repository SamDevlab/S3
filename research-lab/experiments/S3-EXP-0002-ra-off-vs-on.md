# S3-EXP-0002 — RA OFF vs RA ON as a causal control

```text
STATUS=PLANNED
RELATED_ZETTEL=S3-ZK-0006,S3-ZK-0013,S3-ZK-0009
```

## Question

How much of the remaining representative frame traffic exists because the normal benchmark/default path is not using the full whole-function allocation plan, versus because the allocator itself generates true spills?

## Established code fact at P3 anchor

Current `analyze_allocation(function)` already:

- computes CFG-aware liveness;
- builds a whole-function virtual-register interference graph;
- greedily colors vregs;
- handles call-crossing values with a call-aware physical pool;
- forces address-taken referents to stack.

P3's cross-block residence path calls the allocator and then deliberately narrows the selected set.

## Controlled comparison

For identical sources/fixtures and otherwise identical optimization settings collect:

```text
RA_OFF
RA_ON
```

Metrics:

```text
.text bytes
static instructions
MOV count
frame loads
frame stores
rbp-relative loads/stores
rsp-relative loads/stores
true allocation None count
call preservation traffic
wall-clock characterization
```

Required workloads:

```text
jsmn six fixtures
integer loop
branch-heavy scalar probe
loop-carried scalar probe
call-heavy scalar probe
slice/buffer probe
scientific/f64 probe where supported
```

## Interpretation

If RA ON collapses a large fraction of frame traffic without new correctness issues:

```text
DEFAULT_PATH_POLICY / NARROW RESIDENCE
```

becomes a stronger suspect than allocator capability itself.

If RA ON still shows large frame traffic while the allocator reports many `None` colors under genuine pressure:

```text
TRUE_RA_SPILLS
```

become more credible.

If frame traffic stays large despite physical assignments:

```text
EMITTER / FRAME VALIDITY / SNAPSHOT POLICY
```

must be inspected.

## Safety

This experiment is characterization only. Do not change production defaults merely because RA ON is faster until correctness/full regression evidence exists.
