# M1.91-M2.00 Terminal Hardening Evidence

```text
START_HEAD=ac829053b83a241f84700aa962dfdd3bd6cd3d08
FINAL_TESTED_SOURCE_HEAD=1632367cda087bce8feca4e559f2538ca7cbcbea
HISTORICAL_T4_SOURCE_HEAD=eb8ce3e1e8417844810cd4a804c17102bee7fc18
GLOBAL_T4_RUNS_TOTAL=3
ADDITIONAL_T4_RUNS=0
```

## Bounded Results

```text
COMPILEALL=PASS
FOCUSED=70 passed, 0 skipped, 0 failed, exit 0
CROSS_LAYER=120 passed, 1 skipped, 0 failed, exit 0
SMART=11 selected, 11 passed, 0 failed, 0 timeout, exit 0
DIFF_CHECK=PASS
```

The cryptography-dependent cross-layer test is deferred by the environment.
The Linux AArch64 object/link checks are structural PASS; native execution for
Linux AArch64 and macOS ARM64 is deferred by the Windows host.

## Hardening Contracts

```text
H1_DUPLICATE_SELECT_FUTURE=PASS
H2_BOUNDED_SYNC_WAKE_STATE=PASS
H3_REQUEST_BODY_STREAMING=PASS
H4_TLS_HANDSHAKE_BUDGET=PASS
H5_CONSTRAINT_LOCK_SEPARATION=PASS
H6_AARCH64_SEMANTIC_OBJECT_LINK=PASS
H7_PROVENANCE_POLICY_SPLIT=PASS
M1_MIXED_IR_FALLBACK=PASS
M2_GIT_40_HEX_TEST=PASS
M3_REGISTRY_ERROR_TAXONOMY=PASS
M4_DIRECT_TLS_ELF_TESTS=PASS
```

The final source review found zero blockers, highs, or mediums. One low
evidence-scope item remains: native OFF emission is not attempted because the
production emitter requires the self-move-eliminated input. The benchmark
therefore makes no native speedup claim.

## M1.99 Evidence

```text
BENCHMARK_REPO_HEAD=9b506d97d5a8be3282d0cc4df0f4c57abb10b78f
BENCHMARK_S3_HEAD=1632367cda087bce8feca4e559f2538ca7cbcbea
BENCH_CORRECTNESS=PASS
BENCH_TIMING_CLASS=CHARACTERIZATION_ONLY
BENCHMARK_RUN=YES
```

The controlled AssemblyProgram comparison used the same workload with the
optimization disabled and enabled. It covered redundant and non-redundant
self-moves, calls, mutable memory, and control flow. Outputs matched in both
cases; the self-move workload removed two instructions and the workload
without self-moves removed zero. Hosted-emulator timings were recorded with
two warmups, seven repetitions, and 25 loops per sample. Native execution is
deferred because this host is Windows without a Linux x86-64 toolchain.

Historical T4 evidence remains unchanged: three runs total, no additional run.
No publication action was performed.
