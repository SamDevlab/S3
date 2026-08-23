# Milestone 2.68: Assembly Frontend Self-Hosted Closure

M2.68 composes the bounded S3 tokenizer, parser, and frontend into an
executable self-hosted Assembly frontend candidate.

## Scope

The candidate compiles the self-hosted Assembly frontend modules and executes
the composed closure in the hosted Assembly emulator. It compares a
deterministic summary fingerprint with the Python frontend reference for valid
and invalid bounded Assembly sources. The source remains bounded by the
`BoundedText` capacity and uses an explicit candidate execution budget for the
cost of passing that value through the tokenizer and parser.

Parser and frontend state transitions are exercised through the composed S3
implementation. Native emission, fallback activation, incremental build
integration, and performance claims remain out of scope.

## Evidence Contract

- S3 sources: `selfhost/assembly/assembly_tokenizer.s3`,
  `selfhost/assembly/assembly_parser.s3`,
  `selfhost/assembly/assembly_frontend.s3`, and
  `selfhost/frontend/assembly_frontend_closure.s3`.
- Python adapter: `bootstrap/s3/assembly_frontend_closure_candidate.py`.
- Focused contract: `tests/test_m268_assembly_frontend_closure.py`.
- Impact shard: `m268`.
- Valid, invalid-version, deterministic, composition, and bounded-capacity
  contracts are covered.
- No native, benchmark, or performance claim is made.
- Global T4 remains reserved for M3.00.
