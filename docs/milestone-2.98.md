# Milestone 2.98: Bootstrap Reproducibility Seal

M2.98 records a deterministic reproducibility seal for the controlled M2.97
bootstrap admission.

## Contract

- the same admission metadata is materialized twice by the reference;
- both identities must match;
- the S3 candidate computes the same seal identity;
- host-tool requirements remain explicit and native artifact bytes remain
  prohibited.

The seal covers deterministic planning metadata only. It does not execute
bootstrap, compile a source tree, or certify a production artifact.

## Non-claims

M2.98 does not load source, access filesystem/network services, invoke an
assembler/linker, replace the production driver, or claim full self-hosting.
Global T4 and benchmarks remain reserved for M3.00.
