# M1.91-M2.00 Handoff State

This file is the implementation-agent handoff. It describes the state that must
exist before M1.91 source changes begin.

## Remote base prepared

```text
REPOSITORY=SamDevlab/S3
CANONICAL_MAIN=a9e430551f2ee77aa2ef229daf9e967333e83e2c
PREDECESSOR_PR=183_MERGED
CAMPAIGN_BRANCH=feature/m191-m200-autonomous-20260819
BASE_PREPARATION=DOCUMENTATION_ONLY
M191_IMPLEMENTATION_STARTED=NO
PR_CREATED=NO
MERGE=NO
TAG=NO
RELEASE=NO
```

The implementation agent must first synchronize a clean local checkout of the
campaign branch and record the exact remote HEAD before modifying production
source.

## Required read order

Before implementation, read:

1. `reports/roadmap-1.91-2.00-execution/CAMPAIGN_BASELINE.md`
2. `reports/roadmap-1.91-2.00-execution/CAMPAIGN_CONTRACT.md`
3. `reports/roadmap-1.91-2.00-preplan/MILESTONE_CONTRACTS.md`
4. `reports/roadmap-1.91-2.00-preplan/DEPENDENCY_GRAPH.md`
5. `reports/roadmap-1.91-2.00-preplan/RISK_REGISTER.md`
6. `reports/roadmap-1.91-2.00-preplan/BENCHMARK_PLAN.md`
7. predecessor M1.81-M1.90 architecture/closure reports for any subsystem being
   extended.

The agent must inspect the actual source before inventing new abstractions. If
an existing subsystem already provides the required ownership, transport,
backend, package, or release boundary, extend it instead of creating a parallel
hosted model.

## Implementation order lock

```text
M1.91 -> M1.92 -> (M1.93 then M1.94) + (M1.95 then M1.96)
       -> M1.97 -> M1.98 -> M1.99 -> M2.00
```

Research may overlap where safe, but production implementation and milestone
closure remain sequential. Do not begin a later milestone while the previous
one has an unresolved blocker/high finding or missing required focused gate.

## Fail-closed handoff rules

Stop and document rather than silently weaken the contract when any of the
following occurs:

- a required S3 language feature would exist only as a Python sidecar;
- parser/type/lowering/runtime/native behavior disagrees across layers;
- a resource bound would exceed or bypass the `100000` core ceiling without an
  explicit established exception;
- a cryptographic/TLS requirement would need custom or insecure fallback code;
- a benchmark cannot establish equivalent correctness before timing;
- native evidence is unavailable: classify it as deferred, do not fabricate it;
- a test fails or times out: preserve the raw result and isolate/classify it;
- the campaign branch or canonical ancestry differs from the recorded base.

## Expected terminal handoff

The implementation campaign should stop at M2.00 with a clean exact candidate
HEAD, milestone closure evidence, one raw campaign T4 plus bounded triage if
needed, benchmark evidence classified honestly, and no publication side effects.

The final implementation agent must report at least:

```text
FINAL_HEAD=<sha>
WORKTREE_CLEAN=<YES/NO>
M191_M200_MILESTONES_CLOSED=<count>/10
FOCUSED_GATE=<summary>
CROSS_LAYER_GATE=<summary>
SMART_GATE=<summary>
CAMPAIGN_T4_RUNS=<must be 1 at terminal closure>
CAMPAIGN_T4_RESULT=<raw result>
T4_TRIAGE=<summary if needed>
BENCH_CORRECTNESS=<summary>
BENCH_TIMING_CLASS=<CHARACTERIZATION_ONLY/COMPARABLE/NOT_RUN>
BLOCKERS=<count>
HIGH_FINDINGS=<count>
READY_FOR_PR=<YES/NO>
PUSH=<YES/NO>
PR=<YES/NO>
MERGE=NO
TAG=NO
RELEASE=NO
M2_01=NO
```
