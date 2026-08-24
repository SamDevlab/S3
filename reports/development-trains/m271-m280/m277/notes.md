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

- Focused M2.77 contract: PASS, 11 tests on Python 3.11.
- The first focused attempt was interrupted externally; the terminal retry
  passed after correcting S3 control-flow dispatch and return-path handling.
- Compileall, impact metadata, T1 and T3 remain pending until the candidate
  is committed.
- Benchmark: NOT RUN.
- Global T4: NOT RUN; reserved for M3.00.

## STATUS

IMPLEMENTATION_GATES_PENDING
