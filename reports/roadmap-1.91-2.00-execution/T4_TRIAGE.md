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
