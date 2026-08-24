# M2.84 Canonical IR Verifier Candidate

## WHY_NOW

M2.81 and M2.82 define canonical data and expression producers, while M2.83
adds ordered call results. M2.84 supplies the first explicit safety gate
before those pieces are composed.

## ARCHITECTURAL_DECISION

The verifier candidate is intentionally linear and bounded. It records
definition state in fixed S3 storage and reports stable stage codes. CFG
dominance and production verifier integration are deferred.

## TEST_EVIDENCE

- Focused M2.84 contract: PASS, 4 tests on Python 3.11, 3.12 and 3.13.
- Differential reference/candidate proof: PASS.
- `compileall`: PASS.
- `git diff --check`: PASS.
- Impact metadata: PASS.
- T1 affected profile against `a4405c684568defe6b085d3b7cda4fe8ae2ec05e`:
  PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m284` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `d08cf82e75d9b403bc98de8edc4569a72247be3d`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

QUALIFIED_LOCAL
