# Compilation cache

`CompilationCache` is an explicit, process-local cache for repeated compilation
of identical single-source programs. The regular `compile_source(...)` API
remains uncached and stateless.

```python
from bootstrap.s3 import CompilationCache

cache = CompilationCache(max_entries=128)
first = cache.compile(source, "O1")
second = cache.compile(source, "O1")
assert first is second
```

Keys include the SHA-256 of the UTF-8 source, source syntax mode, optimization
level, cache contract version, IR format version, and Assembly format version.
Entries use bounded least-recently-used eviction. Failed compilations are never
stored. `clear()` removes entries and resets counters; `info()` reports hits,
misses, capacity, and current size.

The cache is opt-in because cached `CompilationResult` objects are shared by
identity. Callers must treat them as read-only compiler artifacts. The cache is
not persisted, does not read or write project files, and does not change CLI or
`compile_source(...)` behavior.
