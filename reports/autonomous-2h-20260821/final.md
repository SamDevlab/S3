# Autonomous Correctness, Determinism, and Benchmark Campaign

## Time

```text
START=2026-08-21T17:19:00+00:00
END=2026-08-21T17:37:33+00:00
ELAPSED=18m33s
```

The campaign stopped after the authorized bounded evidence was complete. No
time was added by repeating passing work or padding the campaign.

## S3

```text
BASE_SHA=a651e9b3551f218af1c27bb908e0692880afc4da
S3_DETERMINISM_FIX_SHA=32feb550dcfe01e81eda6e2b4c6f8e1d475bda01
FINAL_TESTED_SOURCE_SHA=32feb550dcfe01e81eda6e2b4c6f8e1d475bda01
BRANCH=fix/licm-determinism-20260821
PR=185
```

The primary Windows checkout was not modified. The correction worktree was
clean after the source commit and remained on the published branch.

## LICM

```text
HASH_SEED_BUG_FIXED=YES
ROOT_CAUSE=unordered CFG successor/predecessor and pre-header iteration in LICM
FILES_CHANGED=bootstrap/s3/ssa_optimizer/loops.py, tests/test_s3_licm.py
REGRESSION_TEST=PASS
```

The fix canonicalizes node/back-edge traversal, predecessor worklist insertion,
and pre-header selection. It does not change invariant eligibility, dominance,
GVN, register allocation, or native instruction semantics.

Focused LICM/SSA/optimizer/pipeline/native tests passed. `compileall` and
`git diff --check` passed. No T4 or full S3 suite was run.

## Cross-Seed Proof

The PR #8 harness was run with fresh processes for `tiny_04_arr`, O1:

```text
seed0 x3: 78519f7c0e4a39694144546e1af7f7a6d86d2884c4430cea849ddf174563dd4d
seed1 x3: 78519f7c0e4a39694144546e1af7f7a6d86d2884c4430cea849ddf174563dd4d
seed42 x3: 78519f7c0e4a39694144546e1af7f7a6d86d2884c4430cea849ddf174563dd4d
```

```text
CROSS_SEED_9_RUN=PASS
CORRECTNESS=9/9 PASS
ASSEMBLY_UNIQUE_DIGESTS=1
OBJECT_UNIQUE_DIGESTS=1
EXECUTABLE_UNIQUE_DIGESTS=1
STRUCTURAL_METRIC_UNIQUE_DIGESTS=1
SOURCE_SHA256=912d758ddb17247bef61e43eff2c271e11ac5b5d3467fb765d6a58174cfad2e1
INSTRUCTION_COUNT=48784
STACK_OPS=7440
BRANCH_COUNT=12524
LOAD_STORE_COUNT=24445
```

All nine manifests recorded S3 SHA `32feb550dcfe01e81eda6e2b4c6f8e1d475bda01`
and benchmark SHA `5fa0285a16056f4f5c92d9d22a4de47373862a8e`. Raw artifacts and
transcripts remain under
`/home/vboxuser/s3-m200-licm-determinism-artifacts-20260821-v4` on the VM.

## Benchmark Infrastructure

```text
ISOLATION=PASS
PROVENANCE=PASS
PR8_SMOKE=PASS
PERFORMANCE_GATE=REOPENED
BENCHMARK_HEAD=5fa0285a16056f4f5c92d9d22a4de47373862a8e
```

The benchmark harness and workloads were not changed. A documentation-only
follow-up branch based on PR #8 was pushed as S3-Benchmarks PR #9; PR #8 was
not merged.

## Performance

The controlled native campaign used the existing runner `--smoke` protocol:
one warmup, five measured repetitions, and 100 internal parses, in order
`A B B A`. A was the M1.90 baseline and B was the deterministic LICM fix.
All four runs passed correctness and used the same Linux x86-64 VM, Python
3.13.15, GCC, benchmark HEAD, fixtures, and runner settings.

```text
EVIDENCE_CLASS=CHARACTERIZATION_ONLY
PERFORMANCE_CAMPAIGN_RUN=YES
CONTROL_C_DRIFT=material; C-O2 geomean A=10573.266 ns, A2=10392.308 ns, B=11179.980 ns, B2=11363.391 ns
S3_O1_A=12932.727 ns
S3_O1_B=12764.712 ns
S3_O1_B2=13040.933 ns
S3_O1_A2=14011.982 ns
S3_O1_DELTA=INCONCLUSIVE
NORMALIZED_DELTA=INCONCLUSIVE
DIRECTION=INCONCLUSIVE
CONFIDENCE=LOW
```

The S3-O1 normalized geomean ratios were A `1.22315`, B `1.14175`, B2
`1.14763`, and A2 `1.34830`. The A/A2 spread is too large for a causal
claim. The LICM correction did not change O1 structural counters or binary
sizes. No native speedup claim is made.

## Optimization #1

```text
ATTEMPTED=NO
KEPT=NO
CHANGE=none; no evidence-backed optimization met the promotion threshold
CORRECTNESS=NOT_APPLICABLE
DETERMINISM=NOT_APPLICABLE
PERFORMANCE_DELTA=NOT_APPLICABLE
```

## Optimization #2

```text
ATTEMPTED=NO
KEPT=NO
CHANGE=none
CORRECTNESS=NOT_APPLICABLE
DETERMINISM=NOT_APPLICABLE
PERFORMANCE_DELTA=NOT_APPLICABLE
```

## Laboratory

```text
CORRECTNESS_STATUS=PASS
REPRODUCIBILITY_STATUS=PASS
NATIVE_CODEGEN_STATUS=PASS
PERFORMANCE_STATUS=CHARACTERIZATION_ONLY_INCONCLUSIVE
PORTABILITY_STATUS=FOLLOWUP_REQUIRED
INITIAL_20_PERCENT_REGRESSION=REJECTED
ABBA_PRE_ISOLATION=INCONCLUSIVE
POST_ISOLATION_PRE_LICM_FIX=INVALID_FOR_PERFORMANCE
POST_LICM_DETERMINISM=PASS
POST_OPTIMIZATION=NOT_RUN
```

## Git

```text
S3_COMMITS=32feb550dcfe01e81eda6e2b4c6f8e1d475bda01 plus documentation commit
BENCHMARK_COMMITS=fd5f5b48f36a1c4805bfbc69590f220e70d65951 (documentation only)
PUSHES=S3 branch pushed normally
PRS=S3 PR #185 open; benchmark PR #8 unchanged; benchmark docs PR #9 open
```

## Next Best Actions

1. Review PR #185 for the LICM determinism and regression-test scope.
2. Re-run a longer paired native protocol only when statistical time permits.
3. Investigate O1 stack and load/store traffic with observer-aware proofs.
4. Expand beyond JSMN before making a general performance claim.
5. Track Python 3.14 behavior as a separate portability follow-up.

## Hard Guarantees

```text
DIRECT_MAIN_PUSH=NO
FORCE_PUSH=NO
MERGE=NO
AUTO_MERGE=NO
TAG=NO
RELEASE=NO
T4_RUNS=0
M2.01_STARTED=NO
```
