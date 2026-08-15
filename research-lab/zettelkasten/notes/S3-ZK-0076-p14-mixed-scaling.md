# S3-ZK-0076 - P14 selected target exhibited mixed scaling

```text
TYPE=PERMANENT
STATUS=SUPPORTED
CREATED=2026-08-15
UPDATED=2026-08-15
SCOPE=P14_EXISTING_JSMN_S3_PARSER_STATE_LOOP
EXACT_WORKLOAD=existing JSMN S3 parser state-loop workload with input-length scaling
COMPILER_SHA=2b38e527760c9242f7bc03e028aef46dfa920ccd
COMPILER_BASE_SHA=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
BENCHMARK_SHA=0cc0ec659857c48febc9e3919791db0701b02516
P14_WORKTREE_HEAD=87a5f8bea876b62b564c729feb6975ecc69bed58
PROTOCOL=warmups=5; repetitions=30; iterations_per_sample=10000; points_bytes=2,7,31,43; Linux; control=C -O2; candidate=S3 -O1 native
SCALING_CLASS=P14_1_MIXED_SCALING
```

## Atomic claim

Within the exact P14 workload and protocol, the S3 candidate exhibited a
reproducible mixed scaling model: a material fixed component plus a
per-input-byte component. This is a bounded empirical result, not a claim
about all S3 workloads or all compiler states.

## Evidence

The fitted S3 slopes were `579.177 ns/byte` for the base and `580.543
ns/byte` for the candidate. The fitted intercepts were `5239.122 ns` and
`5396.294 ns`, respectively. The matched correctness check passed. The
candidate and base marginal checks remained consistent with the mixed-scaling
classification.

The authoritative source is:

```text
File: `C:/Users/samue/Downloads/S3/S3-Benchmarks-p14-lab-20260815/reports/p14-1/P14_1_RESULT.json`
File: `C:/Users/samue/Downloads/S3/S3-Benchmarks-p14-lab-20260815/reports/p14-final/FINAL_P14_REPORT.md`
```

## S3 implication

The target-selection gate must preserve the fixed and input-size-dependent
components separately. A mixed scaling result selects a causal question for
the bounded workload; it does not authorize a transformation and does not
establish legality, realizability, or profitability.

## Falsifier or scope boundary

This note is narrowed, not falsified, by a different workload family,
different compiler candidate, or a protocol that does not reproduce the
declared input-size points. Generalization requires a new matched experiment.

## Provenance and conflict reconciliation

```text
ORIGIN=S3_MEASURED_P14_1
SOURCE_ARTIFACT=P14_1_RESULT.json
SUPPORTS=[[S3-ZK-0029]] [[S3-ZK-0068]] [[S3-ZK-0070]]
CONFLICT_RECONCILIATION=NO_CONFLICT; this records scaling classification only and does not promote a structural or runtime result into an optimization target.
```

## Decision

```text
PERMANENT_WITHIN_DECLARED_SCOPE=YES
WORK_PROVABLY_AVOIDABLE=UNKNOWN
LEGAL_TRANSFORMATION_ESTABLISHED=NO
REALIZABLE_SAVING_ESTABLISHED=NO
PROFITABILITY_ESTABLISHED=NO
```
