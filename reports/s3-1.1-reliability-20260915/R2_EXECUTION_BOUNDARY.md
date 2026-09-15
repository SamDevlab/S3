# R2 execution boundary

GitHub-hosted Actions remain blocked before step assignment under infrastructure issue #284. The current ChatGPT execution runtime also does not have the private S3 repository mounted as a runnable checkout.

Accordingly, R2 does not claim repository pytest execution that did not occur here.

What was directly validated in this session:

- frozen seed derivation vector;
- frozen source SHA-256 vector;
- frozen case-id vector;
- deterministic mutation vector;
- declared feature coverage across the first valid family cycle;
- complete malformed-family cycle;
- bounded deterministic mutation classification;
- absence of clock/PID/Python-random dependencies in generator identity logic;
- syntax provenance against existing stable 1.0 examples/spec surfaces.

What remains executable evidence debt until a repository-capable runner is available:

- `compile_source(...)` for all valid generated families;
- `S3Error` rejection for all malformed generated families;
- `S3Error` rejection for all mutated generated families;
- the full checked-in `tests/test_reliability_generator_v2.py` pytest file.

This debt blocks any claim that R2 itself proved compiler correctness. It does not block landing the deterministic generator infrastructure because no compiler/runtime/backend behavior is modified and all integration checks are preserved as executable tests.
