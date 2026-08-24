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

- Focused M2.84 contract: pending.
- Differential reference/candidate proof: pending.
- `compileall`: pending.
- `git diff --check`: pending.
- T1 affected profile: pending.
- T3 `m284` shard: pending.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

GATES_PENDING
