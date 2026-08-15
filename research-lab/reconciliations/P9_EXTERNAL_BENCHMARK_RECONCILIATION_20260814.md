# P9 External Benchmark Reconciliation

## Scope

This is a bounded reconciliation for `P9_CAUSAL_FRAME_REPRESENTATION_ATTRIBUTION_V1`.
It imports the merged external JSMN evidence into the research lab without
changing compiler production, the benchmark repository, or the external
timing data. It is target-selection input, not a P9 implementation.

## Provenance

```text
S3_MAIN=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
S3_PRE_P8=631b51e70562a33183ac14d0be5bbe2ddd140779
S3_HISTORICAL=85541b782571c80d4857d013d1fb25b4997c1eb9
S3_BENCHMARK_MAIN=0cc0ec659857c48febc9e3919791db0701b02516
BENCHMARK_HARNESS=34bb2c7fe743176fed47116d8ce09d0785d2170e
UPSTREAM_JSMN=25647e692c7906b96ffd2b05ca54c097948e879c
EXTERNAL_REPORT_SHA256=320c869ef0f152b9964cd8c614d7fe9efa05fbe3d72e71843bd18e3dacf99a04
EXTERNAL_RESULT_JSON_SHA256=44e71b911c18fb46e7febfed9cd6a40023ce6b57eeb8c0537e34af52a3ce1494
EXTERNAL_STRUCTURAL_JSON_SHA256=6cb17f72f5d5176531b6c9311688539b0ed280971de92363dfd66c105bd09787
BENCHMARK_PR=3
BENCHMARK_MERGE=0cc0ec659857c48febc9e3919791db0701b02516
```

The report and raw data are in `SamDevlab/S3-Benchmarks` at the merged main
commit. The old `reports/jsmn-baseline.md` remains historical evidence and was
not overwritten.

## Verified external result

The current harness used six shared fixtures and the same Linux host, source
corpus, C comparator, and timing scope for historical, pre-P8, and post-P8 S3.
All three correctness gates passed on status, token count, token attributes,
and deterministic checksum before timing.

```text
HISTORICAL_S3_O1_VS_C_O2=48.8202610254654x
PRE_P8_S3_O1_VS_C_O2=41.54478809000731x
POST_P8_S3_O1_VS_C_O2=39.87592662223254x
POST_P8_S3_O1_NS_PER_PARSE=6842.710068361231
PRE_P8_S3_O1_NS_PER_PARSE=7091.481346091949
P8_ABSOLUTE_RUNTIME_DELTA=-3.5080297837603913%
P8_RATIO_DELTA=-4.017017644088494%
POST_P8_BEST_FIXTURE_RATIO=26.308777739740258x
POST_P8_WORST_FIXTURE_RATIO=66.75012577367399x
```

The result is a modest external improvement with a large residual gap. The
structural probe, over the same six fixtures at O0/O1, changed initialization
check patterns `23172 -> 22812`, static instructions `587952 -> 586152`,
branches `151992 -> 151272`, loads/stores `295500 -> 294780`, and stack ops
`88794 -> 88434`. Those are static assembly counts, not dynamic hardware
measurements.

## Bounded hypotheses

The external result makes the following candidates worth causal testing:

1. broader memory-state and initialization materialization;
2. fixed-array/frame traffic and representation expansion;
3. per-parse fixed-cost expansion where S3 O1 remains close to O0.

These are hypotheses only. The benchmark does not establish that frame traffic
is removable, that loads/stores dominate runtime, that fixed arrays are the
root cause, or that representation expansion is accidental. C O2 is a
counterfactual reference, not the S3 semantic specification. Each difference
must be classified as language-required, implementation-required, accidental,
or unknown at the first lowering boundary where it appears.

## Research constraints

No external benchmark was rerun. No benchmark files were changed in this
reconciliation. GitHub Actions are disabled in both repositories. P9 remains
selection research only:

```text
P9_EXTERNAL_INPUT_READY=YES
P9_SELECTION=NOT_SET
P9_STARTED=NO
PRODUCTION_COMPILER_CHANGED=NO
```

The next experiment must therefore provide semantic-operation-centered
source-to-IR-to-Assembly-to-x86 attribution, a deterministic side-car mapping,
and a validated `MODELLED_NATIVE_DYNAMIC_COUNT` before promoting any target.
