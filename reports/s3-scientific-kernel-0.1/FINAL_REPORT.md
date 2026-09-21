# S3 Scientific Kernel 0.1

Status: complete correctness/native draft checkpoint; PR #309 remains Draft.
Date: 2026-09-20

## Provenance

```text
BASE_PR=308
BASE_HEAD=db0f6b1533938c925daa603209d76d94bbe72485
FUNCTIONAL_HEAD=e07d0b5464bf472b2ca18993f3e196a234ff0fc5
FINAL_TESTED_SOURCE_HEAD=e07d0b5464bf472b2ca18993f3e196a234ff0fc5
FINAL_CANDIDATE_HEAD=e07d0b5464bf472b2ca18993f3e196a234ff0fc5
SOURCE_CHANGED_AFTER_FINAL_GATES=NO
PR=309
PR_STATE=OPEN_DRAFT
PR_MERGED=NO
```

PR #308 was not modified. The new branch was created from its exact final
documentation head and contains one focused implementation commit.

## Capability reuse audit

The required audit is recorded in the Research Lab at
`research-lab/reconciliations/SELFHOST_CAPABILITY_REUSE_AUDIT_20260920.md`.
The durable decision is D-011: a new representation requires a reuse audit
first.

| Capability | Decision |
| --- | --- |
| f64/i64 arithmetic | REUSE_DIRECTLY |
| typed f64/i64 vectors | REUSE_DIRECTLY |
| borrowed references and slices | REUSE_DIRECTLY |
| REFERENCE IR and CALL | REUSE_DIRECTLY |
| TCALL/native ABI | REUSE_DIRECTLY |
| aggregate references/TAGG* | REUSE_DIRECTLY, but not required by this slice |
| sqrt | GENUINELY_MISSING at the base; added as a narrow CALL builtin |
| SSD | ADAPT_EXISTING_CONTRACT; direct f64 vector composition |
| RMSD | source-level composition over SSD and sqrt |

No `NativeIndexedValue`, new representation, new IROpcode, or new
AssemblyOpcode was introduced.

## Implementation

The existing semantic dynamic-builtin table, IR signature table, lowering and
CALL path now carry `sqrt(f64) -> f64`. Hosted execution uses the shared
IEEE-aware `sqrt_f64` contract: NaN stays NaN, negative finite values produce
NaN, positive infinity stays infinity, and signed zero is preserved. The
Linux x86-64 runtime uses direct SSE2 `sqrtsd`; no libm dependency was added.

RMSD is deliberately minimal and source-composed:

```text
sqrt(sum((a[i] - b[i]) * (a[i] - b[i])) / N)
```

The direct vector corpus uses `[1, 2, 3]` and `[2, 4, 6]`: SSD is `14.0` and
RMSD is `sqrt(14/3)`.

## Evidence

```text
DIRECT_F64_VECTOR_SSD_HOSTED=PASS_14_0
SQRT_HOSTED=PASS
SQRT_IEEE_EDGE_CASES=PASS
RMSD_HOSTED=PASS_SQRT_14_OVER_3
LINUX_X86_64_NATIVE=PASS
NATIVE_CANARY=program returned: -1
NATIVE_STDERR=EMPTY
COMPILEALL=PASS
DIFF_CHECK=PASS
```

The Linux proof used the configured `s3-vm` Linux 7.0.0 x86-64 guest and the
published functional commit. The native canary returned a ternary true value
after executing direct f64 vector access, SSD, division, and SSE2 sqrt. The
entry point returns `trit` because standalone native f64 decimal output is not
part of the existing runtime contract.

The final full suite ran exactly once after the source was frozen:

```text
FULL_SUITE_HEAD=e07d0b5464bf472b2ca18993f3e196a234ff0fc5
FULL_SUITE_START=2026-09-20T20:25:40.4271419-03:00
FULL_SUITE_END=2026-09-20T21:40:20.5911519-03:00
FULL_SUITE_EXIT=0
FULL_SUITE_TRANSCRIPT=scratch/s3-scientific-kernel-rmsd-v01-final-full-suite-20260920.txt
FULL_SUITE_TRANSCRIPT_SHA256=d5ee68b275ad2f449b35a0ebf007208595483f32753a4fc579f4448e9d64e16f
```

The inherited corrected-state PR308 full suite also passed before
implementation at `db0f6b1533938c925daa603209d76d94bbe72485`; its transcript
remains preserved separately. No benchmark was run, and no S3-Benchmarks or
Biolab file was changed.

## Boundary and disposition

```text
BENCHMARK=NOT_RUN
RELEASE=NO
TAG=NO
MERGE=NO
SHUTDOWN=NO
READY_FOR_MERGE=NO
```

The implementation is ready for review as a Draft PR, not for merge. A later
benchmark campaign must use a controlled protocol and must not infer timing
claims from this correctness/native evidence.
