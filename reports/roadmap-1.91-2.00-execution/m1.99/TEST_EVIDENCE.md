# M1.99 Test Evidence

The focused regression file `tests/test_m199_codegen_optimization.py` covers
initialized and uninitialized self-moves, the instruction-limit boundary,
deterministic analysis/native text, non-self moves, F64, address-taken
registers, branch joins, calls, x86 logical accounting, and AArch64 semantic
preservation.

Focused gates:

```text
M199_FOCUSED=20 passed, 1 skipped
T2_NATIVE_AND_AARCH64=176 passed, 159 skipped
T3_CROSS_LAYER=67 passed, 1 skipped
COMPILEALL=PASS
DIFF_CHECK=PASS
```

The M1.99 benchmark schema is `s3.m199.self-move.v2`. Its correctness controls
run before timing and prove that the original and candidate Assembly programs
have identical identity, results, uninitialized-register failures, and
instruction-limit failures. The hosted protocol uses five warmups, thirty
alternating repetitions, 25 emulator loops per sample, and records median,
minimum, maximum, IQR, and raw samples.

```text
M199_BASELINE_SHA=2a5f7bdb0e0dfd03fcae5249cb76bff118a642b6
M199_OPTIMIZATION_INTRODUCTION_SHA=a06baa8991dc0217d387bb156fc524caa13c5fd4
M199_CANDIDATE_SHA=7b99ebb9ae4119ecc54b96f78313f0996c476b09
BENCHMARK_REPO_SHA=c13f159bb19f13cac9e83e523b6e392baae71738
M199_BENCH_CORRECTNESS=PASS
BENCH_TIMING_CLASS=CHARACTERIZATION_ONLY
NATIVE_COMPARATIVE_VALID=NO
NATIVE_SPEEDUP_CLAIM=NO
```

The local S3 and benchmark repository HEADs were resolved with Git and checked
against the supplied pins before the protocol ran. The existing M1.81-M1.90
compatibility campaign returned `PASS_WITH_DEFERRED`: 10 passed, 0 failed, and
1 cryptography-provider check deferred by the Windows environment.
