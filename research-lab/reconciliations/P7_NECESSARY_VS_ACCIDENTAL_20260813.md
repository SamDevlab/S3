# P7 necessary vs accidental intermediates reconciliation

## Anchors

```text
BASE=69f5908687123a9ad7a4659b5133f815f08377b1
IMPLEMENTATION_HEAD=b118917ec5a5284899d27b1838712b2e04364caf
PR=176
MERGE_COMMIT=631b51e70562a33183ac14d0be5bbe2ddd140779
ORIGIN_MAIN=631b51e70562a33183ac14d0be5bbe2ddd140779
```

Implementation and merge ancestry are both `YES`. The remote production branch
was preserved. P8 and shutdown remain unauthorized.

## Research result

The fresh 15-workload corpus found 566 static adjacent `TCMP`/`TBR3` pairs and
66 dynamic executions. A comparison result is conditionally accidental only
when the adjacent branch consumes the same destination and liveness proves
there is no successor observer. A successor-use probe retained materialization.

The production candidate fused only this local shape in the x86-64 emitter. It
preserved both instruction-limit checks, initialization checks, integer and f64
ordering, the NaN behavior, and the conservative fallback.

## Validation interpretation

Natural CI for the exact implementation HEAD passed all checks, including
Linux native, numeric closure, differential, renderer, unit, benchmark smoke,
SSA, and Docker capability. The Windows full suite reached 100% with exit 1
for two expected Linux-native toolchain checks. The CI workflow's unit,
renderer, and benchmark filters were reconciled against 2715 collected tests:
2216 + 357 + 151 with nine overlaps, yielding the complete deduplicated union.
Thus the canonical Linux full-suite-equivalent result is exit 0, while the
Windows limitation remains recorded as exit 1.

No comparable new runtime measurement was produced. Broader memory-state,
SSA-staging, RA, frame, and store/reload hypotheses remain open or unproven;
they were not silently converted into P7 scope.
