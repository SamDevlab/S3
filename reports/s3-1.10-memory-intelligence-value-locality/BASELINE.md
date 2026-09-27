# S3 1.10 Baseline

## Control identity

```text
S3_CONTROL_SHA=e27dff1e712e50271df9f860669cd714e28f4ce7
S3_CONTROL_TREE=3e5ddfc7283d8a226505c1cc6680fecf789e147b
S3_CONTROL_BRANCH=feat/s3-1.10-memory-intelligence-value-locality
S3_1_9_PR=323 (MERGED)
BENCH_1_9_PR=27 (MERGED)
BENCH_CAMPAIGN_BASE=b11526443b9f2ac50f2ffdd3c4a6c1d0a2471152
BENCH_CAMPAIGN_TREE=0b4f917abc036ce268e85c2230434f2598170cf4
```

The S3 control tree is identical to the merged #323 head tree
`93d59631a0e81ab1bc905a2eec4d0c4c15846d0e` (`3e5ddfc...`). The #323 merge
adds research tools, tests, reports, and evidence only; its diff contains no
compiler, runtime, standard-library, or production optimizer source changes.
The Benchmarks control tree is identical to merged #27 head
`116b701997cf4d4f5c941115b62825e04a5280b9` (`0b4f917...`). It adds the
independent executor, tests, and research evidence.

The inherited 1.9 native results were generated against S3
`211b1aecec756be42516322429720018f54001e7`, tree
`08289d214832e856d46e14ef941239649e9f4063`. This is before #323's research
additions. Reusing those measurements as the 1.10 control is justified for
compiler-output comparisons because the exact merged #323 tree adds no
production source. The identity difference is retained here; these results
are not represented as a fresh run whose reported source commit is
`e27dff1e...`.

## Inherited native and runtime observations

The pinned characterization used Linux x86-64, O1, PER, three warmups, 21
samples, 1,000 iterations per sample, paired-order seed 1501, and 10,000
bootstrap resamples. Correctness gates preceded timing. Compilation/setup were
excluded; same-process scalar C ABI calls were included equally. This is
workload-specific characterization, not a general speedup claim. PMU was
unavailable by policy (`perf_event_paranoid=4`).

| Workload | `.text` bytes | ELF bytes | Exported function bytes | Instructions | Memory-operand instructions | Branches | Calls | Frame bytes | PER median ns/call |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| energy | 36,304 | 160,584 | 15,179 | 2,754 | 953 | 789 | 1 | 2,144 | 19,056.135 |
| point cloud | 58,112 | 258,832 | 26,063 | 4,732 | 1,601 | 1,367 | 1 | 3,648 | 13,371.121 |
| raster | 68,491 | 312,136 | 31,216 | 5,666 | 1,898 | 1,715 | 1 | 4,192 | 12,813.622 |

The native Observatory v4 reports the whole standalone object's `.text`, a
different accounting scope from the FFI workload symbol:

| Workload | `.text` bytes | Native instructions | Origin-mapped instructions | Mapped fraction | Attributed / unmapped / undecoded bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| point cloud | 58,106 | 11,151 | 4,216 | 37.8083% | 22,864 / 35,242 / 0 |
| raster | 68,482 | 13,034 | 5,125 | 39.3202% | 27,721 / 40,761 / 0 |
| energy | 36,295 | 7,239 | 2,506 | 34.6180% | 13,525 / 22,770 / 0 |

Logical dynamic block profiling is correctness-checked but is not a hardware
retired-instruction count, PMU profile, or cycle attribution. Estimated
structural weights are energy 140,398, point cloud 121,197, and raster 85,806.
Memory-origin categories contribute approximately 48-52% of that structural
weight. This does not establish memory as the cause of 48-52% of runtime.

Reference diagnostics model 8/8 references with known origins and `NO_ESCAPE`
(3 mutable); they do not authorize transformations. The 1.9 same-block
exact-cell mutable-load forwarding experiment found 0 eligible sites among
220 loads and is rejected for that exact rule/workload set only. The three
vector reports classify 5 loops as `UNKNOWN`, 0 vectorizable, and 0 proven
illegal. Static allocation reported 1,024 virtual registers, six
stack-resident virtuals in one function, peak-live 11; dynamic spills were
not measured.

## Evidence provenance

Canonical evidence already present in the 1.9 report tree is referenced, not
copied or regenerated:

| Evidence | Canonical Git path | Canonical bytes | Canonical SHA-256 |
| --- | --- | ---: | --- |
| Native workload timing/object report | `reports/s3-1.9-native-observatory-optimization-discovery/evidence/baseline/native-workload-benchmark-v1.json` | 70,158 | `6ddd6fb9a8fd6a3c656b6ac0970d1e5ba5f44e05cea59da8aaefd888cb15deaa` |
| Dynamic structural profile | `reports/s3-1.9-native-observatory-optimization-discovery/evidence/profiling/logical-dynamic-profile-v3.json` | 54,863 | `2bbfd0585486f0705cd80cb4abb311ff05813a7b95acdbd50223a92c7b44b88e` |
| Observatory v4: energy | `reports/s3-1.9-native-observatory-optimization-discovery/evidence/observatory/energy-native-observatory-v4.json` | 4,774,158 | `f4794705de73e4a4e4f77607c757a585e3185376eaa5a99fa37c820947238eb2` |
| Observatory v4: point cloud | `reports/s3-1.9-native-observatory-optimization-discovery/evidence/observatory/point-cloud-native-observatory-v4.json` | 7,309,747 | `4a02da5d8e65194e018ca3f902a62a192d04442d81bc1a6a7898ca34d106e426` |
| Observatory v4: raster | `reports/s3-1.9-native-observatory-optimization-discovery/evidence/observatory/raster-native-observatory-v4.json` | 8,736,986 | `6a3eb1c63c54a031d47064ddf8574df650cdf6a184e0dd4e0259b69cad3c31f2` |
| References: energy | `reports/s3-1.9-native-observatory-optimization-discovery/evidence/references/energy.pv-timeseries-aggregation.v1-references-v1.json` | 7,384 | `b07dd53ce817c6b85a65c5b9821025941df044544c3ae78d416d602b753ff867` |
| References: point cloud | `reports/s3-1.9-native-observatory-optimization-discovery/evidence/references/engineering.point-cloud-summary.v1-references-v1.json` | 6,688 | `62b2a4af2a4ef57bdb75ec6ca4b65bd517c02ecc709c5d24098dfc1cfdf4ecbe` |
| References: raster | `reports/s3-1.9-native-observatory-optimization-discovery/evidence/references/geospatial.raster-window-statistics.v1-references-v1.json` | 13,466 | `bfcb0b6171d4a2af0f422bd55de2e2e6d13da00af872c3ea6d89c0bfbda20b1d` |
| Vector: energy | `reports/s3-1.9-native-observatory-optimization-discovery/evidence/vector-legality/energy.pv-timeseries-aggregation.v1-vector-legality-v1.json` | 3,676 | `5b1ffe09b118971490dacd83f592814f64b2bda52fd6313ff99fbff6123687b6` |
| Vector: point cloud | `reports/s3-1.9-native-observatory-optimization-discovery/evidence/vector-legality/engineering.point-cloud-summary.v1-vector-legality-v1.json` | 4,925 | `580502cdb5244fec48c2677f35584d96ec6579779bfa20d4b97d2cf9fb4312ff` |
| Vector: raster | `reports/s3-1.9-native-observatory-optimization-discovery/evidence/vector-legality/geospatial.raster-window-statistics.v1-vector-legality-v1.json` | 7,535 | `0139e0c678e83930bd070f2f1c5113c03774dc59e7567657aded82d79bd683fa` |

The large Observatory reports are preserved because they contain instruction
origin rows and object provenance needed for audit. New iterations will not
duplicate these artifacts unless they represent a distinct experiment or
independent result.

## Baseline status

```text
CONTROL_WORKTREE_CLEAN_AT_CAMPAIGN_START=YES
CONTROL_MATCHED_ORIGIN_MAIN_AT_CAMPAIGN_START=YES
PRODUCTION_SOURCE_CHANGED=NO
INHERITED_NATIVE_BASELINE=VALID_WITH_SOURCE_IDENTITY_CAVEAT
FRESH_NATIVE_RERUN_AT_MERGE_COMMIT=NO
BASELINE_CAPTURED_BEFORE_1_10_SOURCE_EDITS=YES
PMU=UNAVAILABLE_BY_POLICY
```

At this checkpoint, no 1.10 compiler source or new benchmark was run. The
baseline explicitly inherits pinned 1.9 observations because the merged
compiler production sources are identical. Byte counts and SHA-256 values in
the evidence table are computed over canonical Git blob bytes, avoiding
Windows checkout line-ending changes. Future candidate comparisons must pin
both source identity and workload/protocol and must pass correctness before
timing.
