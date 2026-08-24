# Milestone 2.96: Driver Artifact Handoff

M2.96 defines the deterministic handoff between the bounded compiler driver
and a later host tool or bootstrap stage.

## Contract

- handoff format is `s3.driver-artifact.v1`;
- workspace and driver identities remain part of the artifact provenance;
- Assembly text is parsed and verified again at the handoff boundary;
- target selection remains explicit;
- `host_tool_required=true` and `native_artifact=None` remain visible;
- the S3 candidate computes the same handoff identity from host-provided
  metadata.

## Non-claims

M2.96 does not write artifacts, load source, invoke an assembler/linker or
runtime, replace the production driver, or claim full self-hosting. Global T4
and benchmarks remain reserved for M3.00.
