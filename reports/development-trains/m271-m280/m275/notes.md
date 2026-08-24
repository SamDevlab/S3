# M2.75 Bounded Function Signature and Call Candidate

## WHY_NOW

M2.73 established scalar type compatibility and M2.74 established place and
reference capabilities. M2.75 adds the bounded declaration and call contract
needed before function semantics can be composed with those checks.

## ARCHITECTURAL_DECISION

The candidate uses fixed-size declaration and parameter tables. A call is
accepted only when the identifier, arity and ordered scalar types match exactly.
There is no implicit conversion, promotion or fallback resolution. Duplicate
declarations and malformed inputs are rejected deterministically.

## IMPLEMENTATION_SUMMARY

- Added `selfhost/semantic/function_call_candidate.s3`.
- Added `bootstrap/s3/function_call_candidate.py`.
- Added focused differential coverage for accepted calls, unknown functions,
  arity/type mismatches, duplicate identifiers and maximum bounds.
- Added M2.75 smart-impact metadata.
- Preserved Python as the reference/default compiler path.

## TEST_EVIDENCE

- Focused M2.75 contract: PASS, 12 tests on Python 3.11, 3.12 and 3.13.
- `python -m compileall -q bootstrap/s3 tools`: PASS.
- `git diff --check`: PASS.
- T1 affected profile: PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m275` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `2a8aaf6861a02b4e434550ae0ab22b1c077d50aa`.
- Documentation may receive a later candidate commit; source gates remain tied
  to the final tested source head.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

QUALIFIED_LOCAL
