# Native Program Frontend Campaign Reconciliation

Date: 2026-09-20

## Provenance

```text
SOURCE_BASE_PR=303
SOURCE_BASE_BRANCH=feat/s3-native-statement-sequence
SOURCE_BASE_HEAD=6231eb676ea3f8a67461a2bd2d6db82aea753f86
CAMPAIGN_BRANCH=feat/s3-native-program-frontend
CAMPAIGN_PR=304
CAMPAIGN_PR_STATE=OPEN_DRAFT
CAMPAIGN_PR_HEAD=bf79e618c64b96d2be5640b4f2949b829df10b5c
NATIVE_CANDIDATE_SHA=86d86bd45b6d073d66ed1e4165d51be63baddccac2faa03fc4307eb8fb4d3244
NATIVE_CANDIDATE_BYTES=190795
S3_BENCHMARKS_CHANGED=NO
```

The functional branch remains separate from the research branch. No merge,
release, tag, benchmark, or full-suite run was performed for this campaign.

## Capability closure

```text
NATIVE_LOCAL_BINDING=PASS
NATIVE_MULTI_STATEMENT_LOCALS=PASS
NATIVE_BINDING_IDENTIFIER_INTEGRATION=PASS
NATIVE_ASSIGNMENT=PASS
NATIVE_PARAMETERS=PASS
NATIVE_FUNCTION_CALLS=PASS
NATIVE_REQUIRED_EXPRESSION_EXPANSION=PASS_FOR_I64_LITERAL_IDENTIFIER_ADD_MUL_GROUPING_LT_GT
NATIVE_NESTED_BLOCKS=PASS_FOR_BOUNDED_STRUCTURAL_SLICE
NATIVE_CONTROL_FLOW=PASS_FOR_BOUNDED_WHILE_STRUCTURAL_SLICE
NATIVE_REAL_MULTI_FUNCTION_PROGRAM=PASS_REPRESENTATIONAL
FIRST_REAL_PROGRAM_SOURCE=two typed i64-parameter add function plus main with locals and add(40, 2)
FIRST_REAL_PROGRAM_STRUCTURE=functions, typed parameters, local declaration, binary expression, call arguments, returns
FIRST_REAL_PROGRAM_DIGEST=352245631123949995
FIRST_REAL_PROGRAM_RESULT=NOT_EXECUTABLE_YET
```

The native S3 path parses direct token identities and source spans and computes
a deterministic structural digest. It does not call `GenericLexer`,
`GenericParser`, `tokenize`, `parse_tokens`, a hosted AST, or a Python semantic
fallback. Hosted parsing is used only as an independent differential oracle in
the focused tests.

```text
S3_NATIVE_LEXER=PARTIAL_SOURCE_TOKEN_SUBSET
S3_NATIVE_PARSER=PARTIAL_PROGRAM_STRUCTURE_SUBSET
S3_NATIVE_PROGRAM_FRONTEND=PASS_FOR_REPRESENTATIONAL_SUBSET
REFERENCE_FALLBACK=NONE
ANTI_FALLBACK_TESTS=PASS
HOST_EXECUTION_SUPPORT=PRESENT_FOR_TEST_HARNESS_AND_NATIVE_TOOLCHAIN
HOST_SEMANTIC_DECISIONS=STILL_PRESENT_IN_ORACLE_AND_UNIMPLEMENTED_NATIVE_SEMANTIC_LAYER
```

## Scientific-kernel requirement gate

The RMSD-like requirement map is intentionally workload-driven rather than a
promise to implement the kernel in this PR:

| Requirement | Status | Evidence or boundary |
| --- | --- | --- |
| Functions | SUPPORTED | Multi-function structural parser and call fixtures |
| Locals | SUPPORTED | Typed immutable/mutable bindings and ordered statements |
| Assignment | SUPPORTED | Source-derived mutable assignment fixture |
| Loops | PARTIAL | `while` condition/body/outer continuation represented; no native semantic execution |
| f64 | MISSING | Native frontend slice is i64-only |
| Indexed data | MISSING | No native array/index expression representation in this slice |
| Arrays or equivalent | MISSING | No native data layout or runtime ownership path |
| Calls | SUPPORTED_REPRESENTATION | Typed function/call argument structure is preserved |
| sqrt or equivalent | MISSING | No native math primitive or lowering path |
| Output | MISSING_FOR_NATIVE_PROGRAM | No native semantic/lowering/execution/output pipeline |

```text
SCIENTIFIC_KERNEL_REQUIREMENT_MAP=COMPLETE
SCIENTIFIC_KERNEL_READINESS=BLOCKED_ARCHITECTURALLY
SCIENTIFIC_MICROKERNEL_EXECUTED=NO
SCIENTIFIC_MICROKERNEL_KIND=NONE
FIRST_MISSING_SCIENTIFIC_CAPABILITY=NATIVE_SEMANTIC_LOWERING_AND_EXECUTION_WITH_F64_INDEXED_DATA_AND_MATH
ARCHITECTURAL_BLOCKER=the current slice stops at structural digest and has no native semantic, lowering, runtime data-layout, f64, indexed-data, or math contracts
MINIMUM_NEXT_CAMPAIGN=design and implement a separately authorized semantic/lowering/runtime vertical slice, beginning with explicit numeric and owned-data contracts
```

This is a scope frontier, not evidence that the language cannot express the
workload. Implementing it here would require more than a parser extension and
would risk inventing runtime and ABI rules without an approved contract.

## Validation

```text
WINDOWS_FOCUSED=PASS
FRONTEND_CHECKPOINT_TESTS=PASS
WINDOWS_FOCUSED_COMMAND=python -m pytest tests/test_native_frontend_slice.py -q
NATIVE_LINUX_QUALIFICATION=PASS
NATIVE_LINUX_TEST_COUNT=the focused file passed with exit 0 on Linux x86-64; pytest did not print a count in quiet mode
NATIVE_LINUX_HEAD=bf79e618c64b96d2be5640b4f2949b829df10b5c
COMPILEALL=PASS
DIFF_CHECK=PASS
FULL_SUITE=PASS
FULL_SUITE_HEAD=bf79e618c64b96d2be5640b4f2949b829df10b5c
FULL_SUITE_RESULT=4002 passed, 311 skipped, 572 subtests passed
FULL_SUITE_EXIT=0
FULL_SUITE_DURATION_SECONDS=4952.20
FULL_SUITE_TRANSCRIPT=C:/Users/samue/AppData/Local/Temp/s3-pr304-full-suite-20260920-060307.txt
```

The PR's natural GitHub Actions run failed before execution: all observed jobs
completed in 1-8 seconds with `steps=[]`. This is recorded as infrastructure
dispatch failure, not a compiler or test failure. No rerun was issued.

```text
REMOTE_CHECKS=FAIL_PRE_EXECUTION
REMOTE_FAILURE_CAUSE=INFRA_DISPATCH
STEPS_STARTED=NO
REMOTE_TEST_EXECUTED=NO
```

## Knowledge closure

The campaign strengthens IC-012 only within its existing scope: a native
frontend should replace one semantic layer at a time and remain differentially
checked. It supplies bounded evidence relevant to IC-013's evaluator/compiler
agreement question but does not justify an independent evaluator or any
promotion. It provides early evidence for IC-015 and IC-016's workload-driven
selection discipline because the scientific requirement map stops at the
first missing execution/data capabilities instead of adding syntax for its own
sake. IC-014 is unchanged: all implemented signatures remain explicitly typed.

```text
INSIGHT_CANDIDATES_STRENGTHENED=IC-012 boundedly; IC-015 and IC-016 directionally
INSIGHT_CANDIDATES_WEAKENED=none
NEW_ZETTELS=none
NEW_NEGATIVE_RESULTS=native structural representation does not imply native semantic execution or scientific-kernel readiness; remote CI dispatch did not execute tests
WHAT_WORKED=source-derived native token/program parsing; differential structural digests; focused Windows and Linux x86-64 validation
WHAT_FAILED=remote CI dispatch before any step; native semantic/lowering/execution remains outside this slice
WHAT_WAS_FALSIFIED=the assumption that adding calls and loops alone would establish a runnable scientific workload
WHAT_REMAINS_UNKNOWN=native semantic/lowering ABI design, f64 representation, indexed-data runtime contract, math primitive contract, and native output execution
```

No production compiler path, benchmark repository, or canonical source was
modified by the research reconciliation.
