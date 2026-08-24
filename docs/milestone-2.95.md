# Milestone 2.95: Bounded Compiler Driver

M2.95 composes the source/workspace boundary with the existing bounded IR,
Assembly verification and native emission contracts.

## Contract

- the driver accepts a host-validated `WorkspaceBoundaryPlan`;
- canonical IR is verified before Assembly emission;
- emitted Assembly is verified before native planning;
- target selection remains explicit and unsupported targets fail closed;
- the result is a deterministic plan with `host_tool_required=true` and no
  native artifact;
- the S3 candidate compares the composition identity supplied by the host.

## Non-claims

M2.95 does not load source, invoke a filesystem/network service, invoke an
assembler or linker, replace the production driver, or claim full self-hosting.
It is a composition checkpoint for the later bootstrap stages. Global T4 and
benchmarks remain reserved for M3.00.
