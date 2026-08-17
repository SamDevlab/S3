# Milestone 1.45 - Deterministic Build Graph and Local Lockfile

Status: COMPLETE.

## Delivered contract

- `s3.toml` project, target, profile, unit, and foreign-library records;
- local relative unit/source paths with project/unit isolation boundaries;
- dependency-first deterministic topological build plan;
- missing dependency and cycle diagnostics;
- content hashes for source and foreign-library bytes;
- graph, per-unit artifact, and overall artifact identities;
- canonical `s3.lock.json` serialization;
- deterministic source loading for the existing multi-module compiler;
- target/profile rejection through the existing target catalog and optimizer
  contract.

No remote resolver, public registry, semantic-version ecosystem, or
incremental compiler internals were introduced.

## Verification gates

- focused M1.45 build-graph tests: PASS (6 tests);
- same graph from different roots: identical lock text/hash/artifact identity;
- independent source manifest hash comparison: PASS;
- hosted multi-unit compilation and IR execution: PASS (2);
- missing dependency, cycle, target, and path-boundary rejection: PASS;
- explicit foreign-library binding and lock identity: PASS;
- Linux x86-64 native multi-unit fixture: PASS (program returned 2);
- compileall: PASS;
- diff check: PASS;
- full suite: terminal exit 0;
- no benchmark, remote write, Docker, virtualization, or shutdown action.

## Boundary

M1.45 is closed. The next milestone is M1.46, the user-facing reproducible
S3 test runner. The lockfile is local and content-addressed; it is not a
package registry or a remote dependency manager.
