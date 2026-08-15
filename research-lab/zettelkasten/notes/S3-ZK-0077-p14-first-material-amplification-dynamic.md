# S3-ZK-0077 - P14 first material amplification was dynamic execution

```text
TYPE=PERMANENT
STATUS=SUPPORTED
CREATED=2026-08-15
UPDATED=2026-08-15
SCOPE=P14_REPRESENTATIVE_JSMN_S3_PARSER_STATE_LOOP
EXACT_WORKLOAD=tiny/tiny_03_pair.json, representative input with 7 bytes
COMPILER_SHA=2b38e527760c9242f7bc03e028aef46dfa920ccd
COMPILER_BASE_SHA=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
BENCHMARK_SHA=0cc0ec659857c48febc9e3919791db0701b02516
P14_WORKTREE_HEAD=87a5f8bea876b62b564c729feb6975ecc69bed58
PROTOCOL=P14_2 marginal funnel; representative input; matched base/candidate; Linux native; no production code change
FIRST_MATERIAL_AMPLIFICATION_STAGE=DYNAMIC_EXECUTION
```

## Atomic claim

For the declared P14 representative input and compiler pair, the first
material amplification in the semantic-to-native funnel was observed at
dynamic execution. The preceding typed IR, SSA, de-SSA and Assembly counts
did not show a per-input-byte marginal increase in the measured funnel.

## Evidence

The P14.2 funnel recorded `0.0` marginal per input byte for typed IR, SSA,
de-SSA IR, Assembly IR and static native x86 instructions, while the S3
runtime model recorded `579.177 ns/byte` for the base and `580.543 ns/byte`
for the candidate. The same funnel recorded native x86 loads/stores as
`24432`, stack operations as `7345`, and branches as `12498` for the
representative input. This is stage attribution, not a proof that the
dynamic work is removable.

The authoritative source is:

```text
File: `C:/Users/samue/Downloads/S3/S3-Benchmarks-p14-lab-20260815/reports/p14-2/P14_2_RESULT.json`
File: `C:/Users/samue/Downloads/S3/S3-Benchmarks-p14-lab-20260815/reports/p14-final/FINAL_P14_REPORT.md`
```

## S3 implication

Future causal analysis must retain the funnel boundary. Static equality or
reduction before dynamic execution cannot be used as a substitute for a
dynamic mechanism and correctness proof. The result narrows where to ask the
next question, but it does not identify a legal or profitable rewrite.

## Falsifier or scope boundary

The claim is bounded to the declared representative input, compiler pair,
and P14.2 funnel. A new compiler SHA, workload class, or instrumented funnel
could move the first material boundary and would require a new note or a
scoped extension.

## Provenance and conflict reconciliation

```text
ORIGIN=S3_MEASURED_P14_2
SOURCE_ARTIFACT=P14_2_RESULT.json
SUPPORTS=[[S3-ZK-0067]] [[S3-ZK-0068]] [[S3-ZK-0029]]
CONFLICT_RECONCILIATION=NO_CONFLICT; the dynamic boundary complements, and does not replace, earlier stage-specific causal evidence.
```

## Decision

```text
PERMANENT_WITHIN_DECLARED_SCOPE=YES
WORK_PROVABLY_AVOIDABLE=UNKNOWN
LEGAL_TRANSFORMATION_ESTABLISHED=NO
REALIZABLE_SAVING_ESTABLISHED=NO
PROFITABILITY_ESTABLISHED=NO
```
