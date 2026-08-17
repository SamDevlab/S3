# M1.45 Architecture Preflight

Status: `CLOSED_FOR_IMPLEMENTATION`.

M1.45 is limited to local path dependencies. There is no registry, remote
fetch, semantic-version resolver, or build cache in this milestone.

Normative decisions:

- `s3.toml` and the lockfile are UTF-8, LF, and canonical TOML/JSON-like
  records with lexicographically ordered keys and arrays where order is
  semantic.
- Lockfile version is `1`; hashes use SHA-256 over domain-separated UTF-8
  canonical records.
- Paths are normalized, absolute, and workspace-relative where possible;
  traversal outside the workspace is rejected.
- A graph node is identified by canonical package path plus declared unit
  name. A target/profile is part of artifact identity.
- Dependencies are emitted in stable topological order, ties by node ID.
  Cycles and missing paths are deterministic errors.
- Environment variables, timestamps, host paths, and compiler absolute paths
  are excluded from identity. Foreign libraries require an explicit name,
  target, ABI identity, and declared hash; discovery is not implicit.
- Lock updates are explicit. A build never rewrites the lockfile implicitly.

The existing roadmap remains unchanged; this is a clarification of its local
graph/lockfile contract.
