# S3-ZK-0078 - P14 localized parser-loop load-store mechanism

```text
TYPE=PERMANENT
STATUS=SUPPORTED
CREATED=2026-08-15
UPDATED=2026-08-15
SCOPE=P14_EXISTING_JSMN_S3_PARSER_STATE_LOOP
EXACT_WORKLOAD=tiny/tiny_03_pair.json plus the P14.1 input-length family
COMPILER_SHA=2b38e527760c9242f7bc03e028aef46dfa920ccd
COMPILER_BASE_SHA=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
BENCHMARK_SHA=0cc0ec659857c48febc9e3919791db0701b02516
P14_WORKTREE_HEAD=87a5f8bea876b62b564c729feb6975ecc69bed58
PROTOCOL=P14_1 mixed-scaling protocol plus P14_2 semantic-to-native funnel
LOCALIZED_MECHANISM=repeated per-byte input and token-array load-store materialization in the parser state loop
WORK_PROVABLY_AVOIDABLE=UNKNOWN
```

## Atomic claim

P14 localized the measured dynamic mechanism for the selected workload to
repeated per-byte input and token-array loads/stores in the parser state
loop. The observation is a mechanism localization result. It must not be
renamed as redundant, unnecessary, or avoidable work without an independent
semantic and memory-effect proof.

## Evidence

P14.2 classified the dominant extra work as `LOADS_STORES` and named the
single mechanism above. P14.1 showed the matched per-byte scaling family.
The available evidence does not establish alias freedom, mutation freedom,
reference equivalence, failure-order preservation, or a realizable saving.

The authoritative source is:

```text
File: `C:/Users/samue/Downloads/S3/S3-Benchmarks-p14-lab-20260815/reports/p14-2/P14_2_RESULT.json`
File: `C:/Users/samue/Downloads/S3/S3-Benchmarks-p14-lab-20260815/reports/p14-1/P14_1_RESULT.json`
File: `C:/Users/samue/Downloads/S3/S3-Benchmarks-p14-lab-20260815/reports/p14-final/FINAL_P14_REPORT.md`
```

## S3 implication

The measured mechanism is a bounded target for proof-oriented investigation,
not an optimization target. Repeated addresses, hotness, or a structural
counter reduction alone do not reopen the line. A future study must separate
the observed dynamic event from legality, realizability, and profitability.

## Falsifier or reopen condition

Reopen only with at least one new compiler SHA, workload class, memory
provenance fact, alias fact, mutation fact, semantic proof, or an explicit
explanation of why the current unknown is resolvable. The proof must account
for the invalidators recorded in [[S3-ZK-0079]].

## Provenance and conflict reconciliation

```text
ORIGIN=S3_MEASURED_P14_1_AND_P14_2
SOURCE_ARTIFACT=P14_1_RESULT.json; P14_2_RESULT.json
SUPPORTS=[[S3-ZK-0054]] [[S3-ZK-0055]] [[S3-ZK-0060]] [[S3-ZK-0061]] [[S3-ZK-0070]]
CONFLICT_RECONCILIATION=NO_CONFLICT; localization is retained while avoidability remains explicitly unknown.
```

## Decision

```text
PERMANENT_WITHIN_DECLARED_SCOPE=YES
WORK_PROVABLY_AVOIDABLE=UNKNOWN
LEGAL_TRANSFORMATION_ESTABLISHED=NO
REALIZABLE_SAVING_ESTABLISHED=NO
PROFITABILITY_ESTABLISHED=NO
```
