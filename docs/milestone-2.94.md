# Milestone 2.94: Source/Workspace Boundary

M2.94 defines the boundary at which a host service supplies source metadata to
the S3-authored pipeline.

## Contract

- source units use canonical relative POSIX paths;
- source paths are unique and deterministically ordered;
- every unit carries a validated lowercase SHA-256 source digest;
- the boundary is bounded to eight units;
- `host_service_required` is explicit and always true;
- the candidate receives metadata projections only and computes the same
  deterministic plan identity as the reference.

The boundary does not read source files, inspect the filesystem, access the
network, or claim source loading/self-hosting. A later host service may provide
the validated text and digest records.

## Non-claims

M2.94 does not change the compiler driver, create a filesystem loader, invoke a
network service, or run global T4. M2.95 must build on this boundary only after
M2.94 is integrated.
