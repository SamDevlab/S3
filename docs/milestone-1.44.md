# Milestone 1.44 - Small Layered Standard Library Core

Status: COMPLETE.

## Contract

The v1 standard library is a deterministic, versioned source layout with
explicit module selection:

- `s3.v1.core` provides capability-free scalar helpers;
- `s3.v1.text` provides static-text construction and length;
- `s3.v1.collections` wraps the ordered `i64_map` and `i64_set` APIs;
- `s3.v1.io` wraps resource inspection and close;
- `s3.v1.host` wraps capability grant, open, active, and invoke.

The manifest records each module's exports and capabilities. Only host and
io declare `resource`; no module creates ambient host access. Unsupported
versions and unknown selected modules fail deterministically.

## Verification

- focused standard-library contract tests: PASS (4 tests);
- hosted text/collection cross-module execution: PASS;
- hosted host/io capability wrapper execution: PASS;
- native Linux x86-64 core O0/O1: PASS (4, 4);
- native Linux x86-64 host/io O0/O1: PASS (2, 2);
- unused host symbols absent from the selected core call graph: PASS;
- compileall: PASS;
- diff check: PASS;
- full suite: terminal exit 0;
- no benchmark, remote write, Docker, virtualization, or shutdown action.

The standard-library wrappers reuse the closed source and builtin contracts;
they do not introduce generic syntax, exceptions, or implicit capability
acquisition. Compatibility is versioned: incompatible changes require a new
module namespace/version.

## Boundary

M1.44 is closed. The next milestone is M1.45. A package registry, large
batteries-included library, locale database, and unrestricted OS wrapper
surface are explicitly deferred.
