# ABL V2.2 Shadow Promotion Hardening

V2.2 hardens the two mechanisms with positive V2.1 structural evidence:
`COMPACT_INDEXED_MEMORY` and `PRESSURE_AWARE_SCALAR_REPLACEMENT`. The
experimental comparison is deliberately limited to `BASELINE`, `COMPACT_EA`,
`SCALAR`, and `COMPACT_EA_SCALAR`; frozen research mechanisms are not promoted.

The default x86-64 backend remains baseline. The internal `off`, `shadow`, and
`compact-ea-canary` modes are experimental and unstable. A canary is permitted
only after static safety, correctness, determinism, holdout, negative-case,
and structural gates pass; it never changes the production default.

V2.2 does not use native or VM timing for selection, does not modify
S3-Benchmarks, and does not claim native speedup. P7/P8/P9 correctness is
classified separately and remains deferred when the read-only benchmark
constraint prevents a safe isolated execution.
