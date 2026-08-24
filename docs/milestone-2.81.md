# Milestone 2.81: Canonical S3 IR Data Model

M2.81 defines the first bounded canonical data model for the IR self-hosting
train. It is independent from the public `s3-ir` 0.6.0 serializer and does not
change the compiler production path.

## Contract

- immutable Python reference records describe functions, registers, blocks
  and instructions;
- type and opcode tables have explicit stable numeric order;
- instruction fields are ordered and explicit: opcode, result, operands,
  immediate presence/value and branch targets;
- bounds are finite and fail closed before candidate execution;
- canonical JSON is versioned as `s3-canonical-ir-model` `0.1.0`;
- a deterministic structural identity is compared with the hosted S3
  candidate through the differential harness.

## Evidence

The focused contract is `tests/test_m281_canonical_ir_data_model.py`. The S3
entrypoint is `canonical_ir_model` in
`selfhost/ir/canonical_ir_data_model_candidate.s3`; it validates only the
bounded data shape and computes a deterministic identity.

## Non-claims

M2.81 does not replace the existing IR model or public IR JSON, perform CFG or
type verification, lower source expressions, select the candidate by default,
claim native self-hosting, claim performance improvement or run global T4.
Verifier work begins in M2.84 and lowering work begins in M2.82.
