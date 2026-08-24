# M2.77 Bounded Control-Flow and Return-Path Candidate

## WHY_NOW

M2.76 established deterministic fixed layouts for scalar record and enum
leaves. M2.77 adds the bounded block-flow facts needed to classify required
returns and unreachable statements before later compiler-source closure work.

## ARCHITECTURAL_DECISION

The candidate uses fixed arrays and a maximum of eight statements. Flow is
represented by three stable classes: fallthrough, returns and terminates.
Branch composition is deterministic and conservative: any fallthrough path
keeps the block reachable, while only an all-return branch is classified as a
return. Python and S3 implementations are checked pairwise for the same
bounded inputs.

## IMPLEMENTATION_SUMMARY

- Added `selfhost/semantic/control_flow_candidate.s3`.
- Added `bootstrap/s3/control_flow_candidate.py`.
- Added focused differential coverage for normal, return, termination,
  branch, infinite-loop and unreachable paths.
- Added M2.77 smart-impact metadata.
- Preserved the Python reference/default compiler path.

## TEST_EVIDENCE

- Focused M2.77 contract: PASS, 11 tests on Python 3.11, 3.12 and 3.13.
- The initial candidate run exposed S3 semantic reachability and dispatch
  defects; the bounded candidate was corrected and the focused contract then
  passed without changing production compiler paths.
- `python -m compileall -q bootstrap/s3 tools`: PASS.
- `git diff --check`: PASS.
- T1 affected profile: PASS, 2 selected, 2 passed, 0 failed, 0 timed out.
- T3 `m277` shard: PASS, 1 selected, 1 passed, 0 failed, 0 timed out.
- Final tested source head: `d7e39caff0e8287b694028c2ac7c66798d27f269`.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

QUALIFIED_LOCAL
