# M1.98 Test Evidence

`tests/test_m198_backend_parity.py` covers exact target coverage, hosted
semantic agreement, deterministic matrix output, and fail-closed behavior when
the default registry lacks the cross-platform targets.

The matrix records `STRUCTURAL_ONLY_TOOLCHAIN_DEFERRED` for every target. No
native Linux AArch64 or macOS ARM64 result is inferred from Python-side
assembly generation.
