# Milestone 2.97: Controlled Bootstrap Admission

M2.97 adds a fail-closed admission boundary for a future bootstrap stage.

## Contract

- only `s3.driver-artifact.v1` handoffs are admitted;
- Assembly is parsed and verified at admission;
- target and host-tool requirements remain explicit;
- native artifact bytes are prohibited at this boundary;
- the candidate computes the same deterministic admission identity.

`bootstrap_allowed` means only that the handoff satisfies this bounded
contract. It is not a production or full self-hosting claim.

## Non-claims

M2.97 does not execute bootstrap, load source, invoke filesystem/network
services, invoke a host assembler/linker, or change the production driver.
Global T4 and benchmarks remain reserved for M3.00.
