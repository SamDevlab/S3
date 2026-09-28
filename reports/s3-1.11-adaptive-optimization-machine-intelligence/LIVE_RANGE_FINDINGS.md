# CFG-Aware Liveness Characterization

## Provenance

```text
EXPERIMENT=EXP-S3-111-LIVE-001
S3_CONTROL_SHA=832b1cc04fe1f6174e482eb3a245e08af3d53211
S3_CONTROL_TREE=dc1138890655169088f9371ce32a9050cfc3af8d
TOOL_SHA256=90b404defc6f84652c8b4900377063e06cea5434150236366d5c3f316174c3ef
EVIDENCE_SHA256=73570e15bcccef6f6944a2bec23ee1bfa08a5897e7e3d82539e385841c86f398
TARGET=Linux x86-64
TIMING=NOT_MEASURED
NATIVE_BUILD=NO
```

The experiment reuses S3's CFG-aware Assembly liveness analysis after O1
compilation. It compares the frozen baseline with two existing research-only
candidate transforms. No compiler implementation or production pipeline was
changed. `total_live_boundary_incidence` sums live-set cardinality at each
instruction's before/after boundaries. Maximum within-block boundary span is
reported separately; no block-order concatenation is interpreted as a global
live range. These counts are static and unweighted by dynamic execution.

## Results

Each cell is `total live-boundary incidence / peak live / observed virtual
registers / values live in multiple blocks`.

| Workload | Baseline | SSA substitution | STORE-to-LOAD |
| --- | --- | --- | --- |
| Energy | 4,359 / 10 / 211 / 7 | 4,409 / 10 / 209 / 9 | 4,864 / 13 / 214 / 10 |
| Point cloud | 4,940 / 7 / 368 / 5 | 4,994 / 7 / 366 / 7 | 6,910 / 12 / 376 / 13 |
| Raster | 9,442 / 11 / 432 / 9 | 9,768 / 12 / 426 / 14 | 11,272 / 14 / 437 / 14 |

Both transforms increase aggregate live-boundary incidence on all three
workloads. STORE-to-LOAD increases peak-live values by 3/5/3 and incidence by
505/1,970/1,830. SSA substitution changes incidence by +50/+54/+326; its
raster peak-live count increases by one. This is consistent with the static
pressure regressions already reported for the candidates, but it is not an
independent spill count, a hardware counter, or evidence that longer live
ranges caused the measured point-cloud timing result.

## Decision and next question

```text
LIVE_RANGE_ANALYSIS=SUPPORTED_STRUCTURALLY
LIFETIME_SHRINKING=NOT_EXPERIMENTED
REGISTER_ALLOCATOR_CAUSALITY=NOT_ESTABLISHED
```

The measurement supports that the rewrites expand static live-set occupancy;
it does not show whether delaying definitions, rematerializing values, or
splitting ranges can recover pressure without losing the point-cloud timing
signal. A bounded lifetime intervention must first identify a concrete
eligible site and preserve exact correctness; no transformation is selected
by this characterization.
