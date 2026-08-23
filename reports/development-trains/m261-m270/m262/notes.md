# M2.62 Self-Hosted Parser Candidate

## WHY_NOW

The M2.61 lexer candidate established a bounded token stream. M2.62 adds the
next frontend self-hosting unit by validating a small V0.6 grammar directly in
S3 against the existing Python parser.

## ARCHITECTURAL_DECISION

`selfhost/frontend/parser_candidate.s3` consumes token kinds and token widths,
validates the complete sequence for one function with no parameters and one
primitive-literal return statement, and emits the same deterministic token
fingerprint as the reference. `bootstrap/s3/parser_candidate.py` retains the
Python parser as the reference and runs the candidate through the existing
compiler and hosted emulator. The candidate rejects valid syntax outside this
bounded subset rather than treating it as implicitly supported.

## IMPLEMENTATION_SUMMARY

- Added the S3-authored bounded parser candidate.
- Added the Python adapter and differential evidence object.
- Added contracts for primitive return types, integer/float/string literals,
  exact indentation tokens, rejected expressions, and token limits.
- Added M2.62 impact and shard metadata.
- Preserved fallback, activation, native, and performance policies.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3 tools`: PASS.
- Focused and adjacent tests: 46 passed, 0 failed, 0 skipped.
- M2.62 T2 at source HEAD `bfa9f0f81990055be989b898a333b4ba5333e405`: 1
  selected, 1 passed, 0 failed, 0 timed out.
- M2.62 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone establishes parser correctness
evidence only and makes no native or performance claim.

## T4_STATUS

Not run. The development-train policy reserves global T4 for M3.00.

## STATUS

M2.62 is complete and ready for review. M2.63 remains the next milestone and
must begin only after this milestone is integrated.
