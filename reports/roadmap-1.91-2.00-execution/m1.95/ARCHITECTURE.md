# M1.95 Architecture: Registry v2

`RegistryV2Client` loads an immutable HTTPS-origin-bound index and resolves
exact `(name, version, sha256)` identities through a deterministic depth-first
dependency walk. Duplicate identities, missing dependencies, digest mismatch,
cycles, unsafe object paths, oversized indexes, package graphs, and caches fail
closed. Verified object bytes are retained in a bounded LRU cache; publishing
remains disabled.
