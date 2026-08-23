# Milestone 2.69: Frontend Optional Canary and Python Fallback

M2.69 adds an explicit canary boundary around the composed Assembly frontend
candidate established by M2.68.

## Execution Policy

The Python frontend reference remains the default execution path. The S3
candidate is selected only when the caller explicitly requests
`s3-canary`. A candidate execution error, reference drift, or differential
mismatch immediately returns the Python reference result and records the
fallback reason. No implicit replacement or promotion is introduced.

## Evidence Contract

- Runtime boundary: `bootstrap/s3/assembly_frontend_canary.py`.
- Candidate evidence: `bootstrap/s3/assembly_frontend_closure_candidate.py`.
- Focused contract: `tests/test_m269_frontend_canary.py`.
- Impact shard: `m269`.
- Default Python selection, explicit matching canary selection, candidate
  error fallback, differential mismatch fallback, and invalid-mode rejection
  are covered.
- No native, benchmark, performance, or global T4 claim is made.
- Global T4 remains reserved for M3.00.
