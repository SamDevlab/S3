# Cross-Target Execution Evidence

`bootstrap.s3.cross_target_evidence` is the shared evidence boundary for the
three supported cross-target classes:

- Linux x86-64
- Linux AArch64
- macOS ARM64

Each target is classified independently as `NATIVE`, `EMULATED`,
`STRUCTURAL_ONLY`, or `DEFERRED`. Native classification requires a matching
host target, passing correctness evidence, and passing structural evidence.
Emulation remains distinct from native execution. Structural artifacts without
execution are always `STRUCTURAL_ONLY`, never native PASS.

The aggregate report is deterministic, rejects duplicate target entries, and
adds an explicit `DEFERRED` entry for every target without evidence. Missing or
failed evidence therefore cannot be mistaken for a complete native matrix.

This harness records evidence classification only. It does not create a
cross-compilation toolchain, execute remote workloads, or make a performance
claim.
