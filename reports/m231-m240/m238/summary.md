# M2.38 External Real-World Performance

`M2_38_PERFORMANCE=CHARACTERIZATION_ONLY`

The benchmark Draft PR is `SamDevlab/S3-Benchmarks#11`, commit `ecab204`.
P1 JSMN differential correctness passed for six fixtures with 100% token/error
parity. Native timing was unavailable on the Windows AMD64 host because the
Linux native toolchain was absent. The available M1.99 harness passed its
correctness and provenance checks as hosted Emulator characterization only.
P2-P18 are deferred because executable protocol-compatible workloads are not
present. No native speedup claim is made.
