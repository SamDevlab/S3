# Decision Summary

## Executive Answers

1. **Actual post-1.50 state:** the Python bootstrap compiler is authoritative,
   with bounded dynamic bytes/text and specialized collections implemented;
   the post-1.50 correctness fixes have 27/27 focused evidence and no observed
   fix-only regression. Linux native, Python ABI, TCP, and WASI runtime claims
   remain environment-qualified.
2. **Most important debt:** aggregate ownership. Dynamic owners cannot yet be
   nested in records, arrays, or enums, and the scalar return/IR conventions do
   not provide a complete aggregate ownership ABI.
3. **Faster testing:** use T0/T1/T2 by default, deterministic impact mapping,
   exact fingerprints, per-file outer timeouts, persisted failures, and resume.
   The existing M1.46 semantic runner remains the execution authority.
4. **Full suite:** only merge/release certification, explicit request, global
   parser/semantic/IR impact, or changes that cannot be safely partitioned.
5. **Recommended M1.51:** Composite Owned Values.
6. **M1.52-M1.60:** ownership flow; constrained generic functions; parametric
   records/enums; generic ordered vector; local package dependencies;
   content-addressed incremental builds; bounded LSP V1; canonical source/DX;
   bounded self-hosted manifest/test reader.
7. **Deferred:** Linux native, WASI runtime, Python ABI/TCP environment gates,
   ARM64, Windows/macOS native, concurrency, GC, raw pointers, public registry,
   mature JIT, Docker certification.
8. **User decision:** yes. License intent must be resolved because
   `pyproject.toml`/README say MIT while `LICENSE` is Apache-2.0. No license
   file was changed.

## Research Decisions

- Keep ownership before generics: generic values without aggregate ownership
  would multiply unstable representations and cleanup rules.
- Use constrained monomorphized generic functions first; no traits,
  typeclasses, higher-kinded types, reflection, or dynamic dispatch.
- Put parametric records/enums before generic vectors so nominal layout and
  ownership identity are stable.
- M1.55 should migrate vectors first; maps and sets follow only after the
  vector identity and deterministic key/value representation are proven.
- Package dependencies precede LSP because namespace identity and invalidation
  are prerequisites for trustworthy editor diagnostics.
- M1.57 can reuse M1.45 artifact identity and lockfile inputs without timestamps
  or absolute paths.
- LSP V1 should omit rename, references, and code actions.
- M1.60 should self-host a manifest/test-report reader, with Python oracle and
  fallback, not the compiler.

## Campaign Boundary

This campaign changed no language semantics, normative roadmap, goldens, or
remote state. M1.51 has not started.
