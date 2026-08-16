# Deterministic Build Graph and Local Lockfile

## `s3.toml`

The minimal project shape is:

```toml
[project]
name = "demo"
root = "."
target = "linux-x86_64"
profile = "debug"

[profiles.debug]
optimization = "O0"

[[unit]]
name = "app"
path = "."
sources = ["main.s3"]
dependencies = ["math"]
foreign_libraries = []

[[unit]]
name = "math"
path = "math"
sources = ["math.s3"]
dependencies = []

[[foreign_library]]
name = "libc"
target = "linux-x86_64"
kind = "system"
```

Unit names, dependency names, and foreign-library names are explicit. Paths
are relative and cannot escape the project root; source paths also cannot
escape their unit root. The supported target is resolved from the compiler's
target catalog, and profiles currently accept the compiler's O0/O1 levels.

## Resolution

Resolution validates all references, captures source and local foreign-library
content hashes, and emits a dependency-first topological order. The lexical
tie-breaker makes independent ready units deterministic. A missing reference
or cycle is an error, not an implicit external dependency.

`load_sources()` returns the resolved local sources in that order for the
existing S3 module pipeline. If a source changes after resolution, loading it
fails and requires a fresh graph resolution.

## Lock identity

The canonical JSON lock payload contains:

- format, project, target/profile/optimization, and topological order;
- sorted units with normalized paths, source hashes, dependencies, and foreign
  references;
- sorted foreign declarations and optional local content hashes;
- `graph_sha256`, per-unit artifact identities, and `artifact_identity`.

`lockfile_text` is deterministic across equivalent roots because absolute host
paths are excluded. `write_lockfile()` writes the exact text to a local path.

## Scope

This contract intentionally excludes registry access, remote Git resolution,
semantic-version selection, implicit foreign libraries, and incremental
compiler internals. Those are separate architectural decisions.
