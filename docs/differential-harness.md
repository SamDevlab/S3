# Hosted Differential Harness

`bootstrap.s3.differential.DifferentialHarness` runs a reference and candidate
callable on equivalent independently decoded canonical input. It records the
canonical input bytes and SHA-256, requires canonical provenance, and compares
canonical outputs or normalized exception records. Unsupported input,
provenance, or output values fail closed.

This is a hosted correctness foundation for future self-hosting differential
components. It makes no native or cross-process execution claim.
