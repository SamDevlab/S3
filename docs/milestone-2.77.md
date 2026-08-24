# Milestone 2.77: Control-Flow and Return-Path Analysis

M2.77 adds an S3-authored bounded contract for block termination,
required-return analysis and unreachable-statement classification in the
semantic self-hosting subset.

## Scope

The candidate analyzes up to eight statements in source order. Normal
statements preserve fallthrough. Return and explicit termination statements
close a block. Branch statements combine two bounded flow outcomes: a branch
falls through if either path falls through, returns only when both paths return,
and otherwise terminates. Infinite-loop statements are classified as
terminating for this bounded contract.

Required-return blocks accept only a returning flow. Any statement after a
return or terminating flow is rejected as unreachable. Invalid kinds, branch
metadata, bounds and return requirements fail closed before candidate
execution.

## Evidence Contract

- S3 source: `selfhost/semantic/control_flow_candidate.s3`.
- Python adapter/reference: `bootstrap/s3/control_flow_candidate.py`.
- Focused differential contract: `tests/test_m277_control_flow_candidate.py`.
- Maximum block size: 8 statements.
- Flow codes are bounded to fallthrough, returns and terminates.
- The Python path remains the reference/default compiler path.

## Non-claims

M2.77 does not claim complete language control-flow coverage, loop lowering,
exception or async control flow, native self-hosting, production promotion,
performance improvement or full compiler self-hosting. Those capabilities
remain subsequent semantic and backend work.
