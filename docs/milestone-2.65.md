# Milestone 2.65: Diagnostic Recovery Candidate

M2.65 adds a bounded S3-authored diagnostic classifier and recovery-action
contract for the frontend self-hosting train.

## Scope

The candidate recognizes six stable diagnostic classes spanning lexical,
parsing, and semantic frontend failures. It maps each known code to a compact
category/action contract and rejects unknown codes. The Python adapter extracts
the same bounded codes from reference lexer/parser failures for the focused
source evidence. This milestone does not replace diagnostic rendering, change
the parser, or claim complete Level-H recovery coverage.

## Evidence Contract

- S3 source: `selfhost/frontend/diagnostic_candidate.s3`.
- Python adapter: `bootstrap/s3/diagnostic_candidate.py`.
- Focused contract: `tests/test_m265_diagnostic_candidate.py`.
- Impact shard: `m265`.
- Unknown diagnostics fail closed.
- No native, benchmark, or performance claim is made.
- Global T4 remains reserved for M3.00.
