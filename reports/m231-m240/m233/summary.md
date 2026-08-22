# M2.33 Cross-Target Native Closure

`M2_33_CROSS_TARGET=DEFERRED_BY_ENVIRONMENT`

Target classification is explicit and does not infer execution from an
artifact. Linux AArch64 and macOS ARM64 remain structural/deferred on the
current Windows host; the focused target registration, artifact, and
conformance-contract tests pass.

- `LINUX_X86_64=DEFERRED_BY_ENVIRONMENT`
- `LINUX_AARCH64=STRUCTURAL_ONLY`
- `MACOS_ARM64=DEFERRED_BY_ENVIRONMENT`
- `AARCH64_EXECUTION_TYPE=UNAVAILABLE`
- `CROSS_TARGET_PARITY=PASS_FOR_CLASSIFICATION_CONTRACT`
