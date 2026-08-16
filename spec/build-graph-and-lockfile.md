# M1.45 Build Graph and Lockfile Contract

The project graph is a deterministic directed graph of canonical local units.
The lockfile records version, node identity, dependency edges, target/profile,
foreign ABI declarations, and SHA-256 content identities in canonical order.
The builder rejects traversal paths, missing nodes, cycles, target mismatch,
and undeclared foreign libraries. Lock updates are explicit.
