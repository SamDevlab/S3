# T4 Failure Triage

## Pre-correction run

```text
HEAD=aa14b36b6f82e0a20652aaeb61c1458d697da693
COMMAND=python -m pytest -q
EXIT=1
FAILURES=2
```

The persistent raw output is `T4-20260820-071828.txt`.

## Findings

1. `tests/test_external_jsmn_s3.py::test_s3_jsmn_representative_fixture_is_stable_across_optimization[O1]`
   exposed that the buffer-capture API compiled with `global_dse`, which
   removed frame stores that the explicit capture observer reads. The normal
   optimizer contract was unchanged; capture compilation now disables only
   `global_dse` through an internal pipeline option.
2. `tests/test_s3_static_text_lowering.py::test_lowering_match_expression_can_select_static_string_value`
   exposed that the new `select` token was treated as a global reserved
   identifier. The parser now recognizes `select:` as the statement form and
   accepts `select`/`case` as identifiers in function and expression positions.

## Post-correction proof

The impacted tests, optimizer/context tests, all M1.91-M2.00 focused tests,
`compileall`, and `git diff --check` passed after the correction. The pre-
correction T4 remains historical evidence and is not relabeled as green.

## Second global run

This section records the second global run. It passed on the then-current
candidate but became stale after the M1.93 completeness correction below.

```text
HEAD=b59de94df667c6ba932f02b4551b2f62946c3072
COMMAND=python -m pytest -q
START=2026-08-20T08:27:09.3395072-03:00
END=2026-08-20T09:27:03.0094203-03:00
EXIT=0
REPORT=T4-final-20260820-082709.txt
```

The raw quiet-progress output contains 2910 passing marks and 195 skip marks.
The 195 `s` marks are pytest skip outcomes, not failures, timeouts, or an
unaccounted terminal category.

## Post-certification M1.93 completeness correction

The first local certification exposed one campaign-contract gap: M1.93 had no
closure file and its tests exercised only an injected byte stream, despite the
milestone requiring a real local TCP fixture. Commit
`eb8ce3e1e8417844810cd4a804c17102bee7fc18` added the bounded
`LoopbackHTTPServer`, real loopback request/response and deadline tests, and the
missing closure evidence. The earlier T4 on `b59de94` is therefore stale for
the final candidate, even though it passed.

The replacement campaign-closing T4 was run once on the corrected candidate:

```text
HEAD=eb8ce3e1e8417844810cd4a804c17102bee7fc18
COMMAND=python -m pytest -q
START=2026-08-20T09:35:20.1386347-03:00
END=2026-08-20T10:34:32.5431840-03:00
EXIT=0
REPORT=T4-final-correction-20260820-093520.txt
```

Its raw quiet-progress output contains 2912 passing marks and 195 skip marks.
The 195 `s` marks are pytest skip outcomes, so the authoritative accounting is
`3107 = 2912 + 0 + 0 + 195 + 0`.

## Terminal run accounting

```text
GLOBAL_T4_RUNS_TOTAL=3

T4_RUN_1_ROLE=HISTORICAL_PRE_CORRECTION_FAILURE
T4_RUN_1_HEAD=aa14b36b6f82e0a20652aaeb61c1458d697da693
T4_RUN_1_SELECTED=3105
T4_RUN_1_PASS=2908
T4_RUN_1_FAIL=2
T4_RUN_1_TIMEOUT=0
T4_RUN_1_SKIP=195
T4_RUN_1_EXIT=1

T4_RUN_2_ROLE=STALE
T4_RUN_2_HEAD=b59de94df667c6ba932f02b4551b2f62946c3072
T4_RUN_2_STALE_REASON=M1.93 lacked required real TCP fixture and closure evidence; eb8ce3e added both.
T4_RUN_2_SELECTED=3105
T4_RUN_2_PASS=2910
T4_RUN_2_FAIL=0
T4_RUN_2_TIMEOUT=0
T4_RUN_2_SKIP=195
T4_RUN_2_EXIT=0

T4_RUN_3_ROLE=AUTHORITATIVE
T4_RUN_3_HEAD=eb8ce3e1e8417844810cd4a804c17102bee7fc18
T4_RUN_3_SELECTED=3107
T4_RUN_3_PASS=2912
T4_RUN_3_FAIL=0
T4_RUN_3_TIMEOUT=0
T4_RUN_3_SKIP=195
T4_RUN_3_OTHER=0
T4_RUN_3_EXIT=0
T4_RUN_3_ACCOUNTING_EXACT=YES

T4_TRIAGE_RUN=1
T4_TRIAGE_PASS_IN_ISOLATION=2
T4_TRIAGE_PREEXISTING_TIMEOUT=0
T4_TRIAGE_ENVIRONMENT_DEFERRED=0
T4_TRIAGE_REPRODUCIBLE_FAILURE=2
T4_TRIAGE_UNRESOLVED=0
```

The authoritative third run had no failures or timeouts and required no
failure triage. The two diagnosed cases belong only to run 1; both passed the
post-correction isolated proof.
