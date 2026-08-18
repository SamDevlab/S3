# Post-1.50 Architecture Debt

## Priority 1: Composite Ownership

M1.39 deliberately keeps `bytes` and `text` out of records, static arrays, and
enums. Records/enums use scalar-leaf fixed layouts, while the current IR and
Assembly convention has one scalar return register and no aggregate return ABI.
This blocks larger application data models and is the single largest language
model gap. The missing contract covers move, borrow, clone, drop, branch joins,
early returns, loop backedges, nested aggregates, and allocation failure.

Recommendation: M1.51 defines owned aggregate layout and M1.52 proves control
flow ownership transfer. Keep the public surface closed and explicit; do not
smuggle generics into the ownership milestone.

## Priority 2: Collection Identity

`bootstrap/s3/ir.py` exposes specialized vector/map/set signatures but uses a
common vector-like IR identity. `tryte_vector`, `i64_vector`, `f64_vector`,
`i64_map`, and `i64_set` are useful implemented domains, not a parametric
abstraction. Resolve ownership first, then constrained monomorphized generic
functions, then parametric records/enums, then collections.

## Priority 3: Compiler Module Scale

`semantic.py` is 3,909 lines and carries declaration collection, type identity,
layout, ownership, diagnostics, and expression semantics. It is a maintenance
constraint and a future generic/aggregate-ownership risk, but size alone is not
permission for a refactor. M1.51/M1.52 should add contract-level tests and
stable public queries before any decomposition proposal.

## Priority 4: Package and Build Boundary

M1.45 already supplies a deterministic local graph, topological ordering,
content hashes, lockfile identity, and foreign-library records. It explicitly
does not provide a package manager, registry, download protocol, or namespace
identity across packages. A local path/Git revision dependency model with
offline lock resolution is the smallest useful next step; a public registry is
not required.

## Priority 5: Incremental and Developer Workflow

Artifact identity is already suitable for deterministic invalidation, but the
repository had no impact-aware test workflow or incremental build planner. The
new local `s3test` layer closes the test-loop gap. Build caching should follow
the same content-addressed inputs, excluding timestamps and absolute paths.

## Priority 6: Tooling and Self-Hosting

LSP becomes high-value after project/package identity and stable diagnostics
are available. M1.59 should focus on formatter, project initialization, build/
test/run summaries, and discoverability. M1.60 should target one bounded
self-hosted manifest/test-report reader with Python oracle, exact deterministic
parity, strict memory budget, and fallback to Python. A compiler rewrite is out
of scope.

## Deferred or Explicitly Unsupported

Threads, async runtime, atomics, shared memory, ARM64, Windows/macOS native
backends, public registry, mature JIT, GC, raw pointers, and Docker-dependent
certification remain deferred. WASI, Linux native, and Python ABI have
structural or focused evidence but environment certification remains deferred.
