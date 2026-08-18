# M1.51-M1.60 T4 Triage and Self-Correcting Closure

Status: `IMPLEMENTATION_COMPLETE_WITH_DEFERRED_ENVIRONMENT_CERTIFICATION`

## Authoritative Checkpoint

- Campaign branch: `feature/m151-m160-autonomous-20260817`
- Triage verified HEAD: `fcc173a58e0d55875b5a76be5cea052721edaade`
- Campaign base: `ee6cdb7a2ee22f6c4e64c4091549b2740b963504`
- M1.51A architecture: `ee6cdb7a2ee22f6c4e64c4091549b2740b963504`
- Post-1.50 prerequisite fix: `06430710d05df925912603bd0a788022439079d5`
- Python: `3.11.9`
- Platform: `Windows-10-10.0.26200-SP0`
- Working tree before this report closure: clean

The original T4 evidence remains preserved at
`.s3-test-state/0a36a7f84ce8949d363c711c583a0aa02cb1d43760405f7dfe102e5126003232.json`.
The current smart-test fingerprint is invalid for that report because HEAD
and the dirty evidence payload changed. The runner therefore did not reuse the
stale cache or start a blind full resume.

## Original T4

The only aggregate T4 run was:

`python tools/s3test.py full --format json`

on `c5163032d9c19713f8497d5bf9d15d73f55c6fef`:

- 328 selected
- 298 passed
- 7 failed
- 23 timed out

No raw full T4 restart was performed.

## Seven Failures

The complete machine-readable inventory and matrix are in
`T4_FAILURE_INVENTORY.json` and `T4_FAILURE_MATRIX.json`.

1. JSMN O1 representative fixture: two exact current-HEAD reruns passed;
   `NON_REPRODUCIBLE_TRANSIENT`; no repair.
2. Nested arrays: base passed, final failed, and the M1.51 array guard was
   restored in `f673351236f7d1ca6a69f9537276e7dd98f7e3be`; final exact reruns
   passed.
3. Native nested-record array rejection: `STALE_TEST`; M1.51 permits arrays
   of records; replacement contract passed.
4. Postfix aggregate rejection: `STALE_TEST`; replacement contract passed.
5. Record composition rejection: `STALE_TEST`; replacement contract passed.
6. Member assignment parser rejection: `STALE_TEST`; M1.51 now parses the
   target and semantically rejects an immutable aggregate; replacement contract
   passed.
7. String arrays: base passed, final failed, and the M1.51 string-array guard
   was restored in `f673351236f7d1ca6a69f9537276e7dd98f7e3be`; final exact rerun
   passed.

Counts: 2 M1.51 regressions found and repaired, 4 stale tests corrected, 1
non-reproducible failure, 0 unresolved correctness regressions.

## Twenty-Three Timeouts

All 23 original timeout entries are preserved and classified in
`T4_TIMEOUT_INVENTORY.json` and `T4_TIMEOUT_MATRIX.json`. Every file passed
when run alone on the final HEAD. Therefore:

- `FINAL_TIMEOUTS=0`
- `AGGREGATE_OR_PARALLEL_TIMEOUTS=23`
- `PREEXISTING_TIMEOUTS=0`
- `ENVIRONMENT_TIMEOUTS=0`
- `UNKNOWN_TIMEOUTS=0`

The original timeouts were caused by the smart runner's 60-second per-file
budget and serialized renderer/Assembly cost on Windows. No timeout is
final-only, and none touches an M1.51-M1.60 production path.

## Verification After Triage

- Exact failure reruns: 7 entries processed; JSMN ran twice, repaired/stale
  replacements ran on the final HEAD.
- Timeout file reruns: 23/23 PASS in isolation.
- M1.51 smart shard: 8/8 PASS on `f673351236f7d1ca6a69f9537276e7dd98f7e3be`.
- M1.60 smart shard: 3/3 PASS on `97bf9ada5c7cd60d72a114bfa0671e4b045d4e4e`.
- Directed aggregate/static proof: 15/15 PASS.
- Compileall, diff check, and JSON validation: PASS.
- T1/T2 reruns in this triage: not required; the affected T3 and exact-node
  gates passed.
- Smart resume: not used because the original T4 fingerprint was invalid;
  persisted T4 evidence was consumed and not discarded.

## Certification and Publication

- M1.51-M1.60 regressions: none unresolved.
- Native Linux runtime certification: `DEFERRED_BY_ENVIRONMENT`.
- WASI runtime certification: `DEFERRED_BY_ENVIRONMENT`.
- Benchmarks: `NO`.
- M1.61: not started.
- Ready for publication review: `YES`.
- Remote write, PR, merge, tag, release, and shutdown: `NO`.

## Final Status

`IMPLEMENTATION_COMPLETE_WITH_DEFERRED_ENVIRONMENT_CERTIFICATION`

The implementation line is complete and all 30 original T4 problems are
classified. Remaining deferments are external runtime certifications, not
M1.51-M1.60 correctness regressions.
