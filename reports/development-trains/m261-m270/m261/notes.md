# M2.61 Self-Hosted Lexer Candidate

## WHY_NOW

The frontend self-hosting train begins with a bounded lexer candidate authored
in S3. The candidate must produce independently checkable evidence against the
existing Python lexer before later parser and AST candidates are introduced.

## ARCHITECTURAL_DECISION

`selfhost/frontend/lexer_candidate.s3` is the candidate implementation. It
accepts ASCII source of at most 96 code units and computes a deterministic token
fingerprint for the declared subset. `bootstrap/s3/lexer_candidate.py` runs the
candidate through the existing compiler and hosted emulator, while the Python
lexer remains the reference. `DifferentialHarness` compares the same source,
mode, provenance, and output fingerprint. Unsupported or out-of-bound input is
rejected closed.

## IMPLEMENTATION_SUMMARY

- Added the S3-authored bounded lexer candidate.
- Added the Python adapter and differential evidence object.
- Added focused contracts for identifiers, keywords, numbers, comments,
  delimiters, operators, ordering, and rejection boundaries.
- Added M2.61 impact and shard metadata.
- Preserved fallback, activation, native, and performance policies; no runtime
  candidate is promoted by this milestone.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3 tools`: PASS.
- Focused and adjacent tests: 49 passed, 0 failed, 0 skipped.
- M2.61 T2 at source HEAD `2f58c6e2f49a61d755c175b3922ff2ba0fc794ea`: 1
  selected, 1 passed, 0 failed, 0 timed out.
- M2.61 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone establishes frontend correctness
evidence only and makes no native or performance claim.

## T4_STATUS

Not run. The development-train policy reserves global T4 for M3.00.

## STATUS

M2.61 is complete and ready for review. M2.62 remains the next milestone and
must begin only after this milestone is integrated.
