# S3 1.11 Control Baseline

## Frozen control identity

```text
CAMPAIGN=S3_1_11_ADAPTIVE_OPTIMIZATION_REGISTER_MEMORY_CODESIGN_MACHINE_INTELLIGENCE_AND_EXPERIMENTAL_COMPUTE_FRONTIER
S3_CAMPAIGN_BASE=832b1cc04fe1f6174e482eb3a245e08af3d53211
S3_CONTROL_SHA=832b1cc04fe1f6174e482eb3a245e08af3d53211
S3_CONTROL_TREE=dc1138890655169088f9371ce32a9050cfc3af8d
BENCH_CAMPAIGN_BASE=b3ecb9b2269b583cba0706fd7ed13956a9641512
BENCH_CAMPAIGN_TREE=06316635dfc1830d3ec3955803acb0d168b77a7e
PER_INSTRUCTION_DEFAULT=YES
STRICT_FP_PRESERVED=YES
PRODUCTION_SOURCE_CHANGED=NO
```

The S3 control is merged PR #324. The Bench control is merged PR #28; its
tree is exactly the merged S3-Benchmarks `origin/main` tree. Both campaign
branches were created directly from their respective `origin/main` commits.
The S3 1.10 source freeze is `856bf0cd60c3da6ba701adec73c7858d063739a7`
(`5d7c179ac9df64fad99b7ec140f69571c48b866f`). Comparing its tree with this
control shows only the two 1.10 report files changed after source freeze.

## Capture provenance

The authoritative Linux capture used a clean detached worktree at the exact
control SHA and wrote all output outside the checkout. It completed with exit
zero and the source worktree was clean at both boundaries:

```text
HOST=Linux x86_64
KERNEL=7.0.0-31-generic
PYTHON=3.14.4
CC=Ubuntu cc 15.2.0
CONTROL_WORKTREE=/tmp/s3-1.11-control-clean-832b
OUTPUT_ROOT=/tmp/s3-1.11-baseline-evidence-832b-v2
BASELINE_START_UTC=2026-09-27T23:00:05.774968732Z
BASELINE_END_UTC=2026-09-27T23:00:27.880031525Z
BASELINE_TERMINAL=YES
BASELINE_EXIT=0
SOURCE_WORKTREE_CLEAN_AT_START=YES
SOURCE_WORKTREE_CLEAN_AT_END=YES
PMU=UNAVAILABLE_BY_POLICY
PERF_EVENT_PARANOID=4
```

The earlier output-root attempt that dirtied its checkout is retained as
diagnostic evidence outside this repository and is not the control baseline.
The authoritative native workload JSON records the exact clean Git commit,
tree, workload hashes, correctness, candidate output hashes, protocol, and
timing samples.

## Native characterization

Protocol: Linux x86-64; S3 O1/PER baseline; 3 warmups; 21 samples; 1,000
same-process scalar C-ABI calls per sample; 10,000 paired bootstrap
resamples; setup and compilation excluded; no hardware counters. Values are
workload-specific characterization, not a general speedup claim.

| Workload | Source SHA-256 | Dataset SHA-256 | `.text` bytes | Instructions | Memory refs | Stack refs | Branches | Frame bytes | Median ns/call | Correctness | Native output SHA-256 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| energy aggregation | `a146f2ec7bd7f9bf72ea35c04026174874012acdb31541d805bf5f0a4a613c84` | `dcf7e356a75be9597f2732c1739a2f93f73d657bfdaa4207634aff2e5481afca` | 36,304 | 2,754 | 953 | 907 | 789 | 2,144 | 16,946.870 | PASS_ALL_BUILDS | `5f8ea95fcf8bc698b46f47801ea8e429c41f207813de7942d40c1f186f766a74` |
| point-cloud summary | `59e752e91159ece4e3a813bc8586f338544ddac52e4b5e755a219d85779238e9` | `346178eab37077a8bd7989d60836a2b54fb27948c36dabd18e7a58b2e41042f8` | 58,112 | 4,732 | 1,601 | 1,536 | 1,367 | 3,648 | 13,502.950 | PASS_ALL_BUILDS | `6bdc5b40a566f1b9487ff18c96ceb2a7ab53c740c666b4f8bf10de84bee6dc07` |
| raster statistics | `6d5d8081991d4a2af0f422bd55de2e2e6d13da00af872c3ea6d89c0bfbda20b1d` | `3a182a6f587c30c9f38c0c25dba394729ea4563568dc00e9c3999091a4593f3c` | 68,491 | 5,666 | 1,898 | 1,821 | 1,715 | 4,192 | 11,494.410 | PASS_ALL_BUILDS | `60587afe0ddedafe7e443b119731361cf64228c4ebf13759e7ced80f5e9174dc` |

The workload benchmark JSON is the source of the table; the medians above
were reconciled from its exact `S3_O1_BASELINE` samples. Earlier checkpoint
notes included different medians. Those values are not substituted here:
the preserved raw JSON SHA-256 is
`4b8eabb4f542c93a0bfde3b3736bd8fe26cecea9c1521d636297908ab92556e2`.

## Dynamic structural profile and loop baseline

Logical block entries are measured by instrumentation; the weighted static
machine syntax categories are not hardware retired instructions, runtime
fractions, or PMU data. Totals below are summed from the complete aggregate
category maps, not the report's bounded hot-block display list.

| Workload | Logical blocks | Structural weight | MOVE | CONTROL_FLOW | STACK | UNKNOWN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| energy aggregation | 2,036 | 140,398 | 51,326 | 44,140 | 15,918 | 28,846 |
| point-cloud summary | 1,304 | 121,197 | 43,064 | 38,437 | 14,797 | 24,898 |
| raster statistics | 1,622 | 85,806 | 28,594 | 28,933 | 9,773 | 18,460 |

The combined structural weights are 35.9% MOVE, 31.8% CONTROL_FLOW, 12.4%
STACK, and 20.4% UNKNOWN. This is a static, block-weighted syntax
characterization only; it cannot establish the runtime cost of any category.

The fresh conservative loop reports classify five workload loops as
`UNKNOWN`: one energy, two point-cloud, and two raster. No loop is proven
vectorizable or proven illegal. SIMD is not authorized by this baseline.

## Curated evidence and retention

Committed evidence lives under `evidence/control-832b/`. The full native
observatory JSONs are retained because instruction-origin rows support
future move/control provenance experiments. Raw binaries, generated
assembly, shared libraries, and temporary compiler outputs remain outside
Git. A second exact copy of the committed native-observatory JSONs and the
compact outputs is archived at:

```text
C:\Users\samue\Downloads\S3\scratch\s3-1.11-control-baseline-832b-20260927
```

The external archive contains 20,965,093 bytes. Its `SHA256SUMS.txt` records
the file hashes. The three observatory JSON hashes are:

```text
energy       dfb19b4d779700ac181ad89bc786e9e26da31e072029c9af94adc0db0ca2943e
point-cloud  17f4224028cbebaf541ab2dbc40a4558b3dd046d01a8ce464b6a5cdd0ce29fa2
raster       2f959824c289f72e873ab5853e87eb45b185427ec67ce73c839f0f7061d01a8a
```

Compact baseline hashes:

```text
native workload benchmark  4b8eabb4f542c93a0bfde3b3736bd8fe26cecea9c1521d636297908ab92556e2
logical dynamic profile    cb41a728b1af004835dda6df008db0eed6956165fb2f031a969776a0dd288434
energy vector legality     288fd8af2fa91a888120110d4249d8d3f2d9b2dbb3cedb2e813022e3cec6ab6e
point vector legality      1bdc65068f957488a9e3dc12e597a34af8ed68b7cba76ec4a2c8f1c989ef9be4
raster vector legality     1529fc49b43ef3525c2ccaf675fa745ce827dc7a614b01e1560d0a052832b7e8
```

No compiler production source, optimizer default, PER semantics, or strict-FP
contract changed while capturing this baseline.
