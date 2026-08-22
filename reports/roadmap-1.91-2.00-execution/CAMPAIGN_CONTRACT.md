# M1.91-M2.00 Autonomous Campaign Contract

This file is the execution contract for the autonomous M1.91-M2.00 campaign.
It refines the provisional pre-plan without changing the milestone capability
sequence.

## Execution model

The campaign uses one branch and one final pull request:

`feature/m191-m200-autonomous-20260819`

Milestones are implemented sequentially as reviewable commits on that branch.
The earlier provisional rule requiring a separate branch/merge for every
milestone is superseded **for this campaign only**. Dependency isolation is
preserved by milestone closure gates: M1.N+1 may not begin until M1.N has
focused evidence, cross-layer evidence where applicable, updated architecture
notes, and zero unresolved blocker/high findings.

No milestone may claim completion from documentation, structural metadata, or
hosted Python abstractions when the milestone contract requires first-class S3
language/compiler/runtime/native behavior.

## Milestone sequence

1. M1.91 — `ASYNC_CONTROL_FLOW_AND_SELECT_LANGUAGE_V1`
2. M1.92 — `ASYNC_SYNCHRONIZATION_PRIMITIVES_V1`
3. M1.93 — `STREAMING_HTTP_AND_HTTP_SERVER_V1`
4. M1.94 — `TLS_SERVER_AND_SECURE_CHANNELS_V1`
5. M1.95 — `PACKAGE_RESOLUTION_AND_REMOTE_REGISTRY_V2`
6. M1.96 — `SIGNED_PACKAGE_INDEX_AND_TRUST_POLICY_V1`
7. M1.97 — `AARCH64_NATIVE_OBJECT_AND_LINK_INTEGRATION_V1`
8. M1.98 — `CROSS_PLATFORM_NATIVE_BACKEND_PARITY_V1`
9. M1.99 — `BENCHMARK_DRIVEN_RUNTIME_AND_CODEGEN_OPTIMIZATION_V1`
10. M2.00 — `S3_2_0_RELEASE_CANDIDATE_AND_LANGUAGE_STABILITY_GATE`

The detailed goals/non-goals remain in
`reports/roadmap-1.91-2.00-preplan/MILESTONE_CONTRACTS.md`.

## Global invariants

- Preserve the core instruction/resource ceiling `100000`.
- Preserve deterministic ownership/drop/cancellation semantics established by
  M1.81-M1.90.
- No detached task default, implicit unbounded queue, unbounded parser/frame,
  unbounded network body, unbounded package graph, or unbounded archive input.
- No custom cryptographic primitive or insecure TLS fallback.
- No silent target fallback, host-target confusion, or fake native certificate.
- No public network service is a correctness fixture.
- Environment absence is `DEFERRED`, never silently converted to `PASS`.
- Historical failures/timeouts remain historical facts and are never rewritten.
- No force push, history rewrite, branch deletion, tag, release, package
  publication, or M2.01+ implementation.

## Local test protocol

During each milestone:

- T0: syntax/import/compile sanity when relevant;
- T1: focused unit and contract tests for changed surfaces;
- T2: adjacent compiler/runtime/protocol/ownership integration tests;
- T3: smart/impact-selected cross-layer or native/differential tests when the
  change can affect those layers;
- milestone closure: exact HEAD, focused counts/exits, environment deferments,
  architecture report, and unresolved-finding count are recorded.

Exactly **one campaign-closing T4** is permitted, after M2.00 reaches a final
candidate. T4 is not rerun merely to obtain a green-looking result. Any fail or
timeout remains in the raw result and receives bounded isolation/triage.

Local gates are authoritative for campaign readiness. GitHub Actions/checks are
supplementary unless the repository explicitly adopts a campaign-specific
remote-check requirement. Pending/skipped Actions alone do not invalidate an
otherwise complete local gate.

## Benchmark protocol

Correctness precedes timing. The S3-Benchmarks repository is independent
campaign evidence; benchmark code must pin the exact S3 SHA used.

- M1.91-M1.98: characterization only unless a pinned independent reference
  workload/toolchain exists.
- M1.99: optimization requires an independent pinned reference, reproducible
  before/after protocol, equivalent semantics, and no benchmark-specific
  compiler/runtime special case.
- M2.00: benchmark data is release evidence only when its correctness and
  reproducibility gates are satisfied.

No synthetic timing, public-service dependency, cherry-picked result, or
comparative claim without equivalent pinned reference is acceptable.

## Evidence layout

Each milestone should write under:

`reports/roadmap-1.91-2.00-execution/m1.xx/`

with at least:

- `ARCHITECTURE.md`
- `TEST_EVIDENCE.md`
- `CLOSURE.md`

Campaign-level files should include:

- `CAMPAIGN_BASELINE.md`
- `CAMPAIGN_CONTRACT.md`
- `HANDOFF_STATE.md`
- `FINAL_M191_M200_CERTIFICATION.md` (created only at terminal closure)
- raw T4/triage evidence created only after the single campaign-closing T4.

## Publication boundary

The implementation agent may create local commits on the campaign branch. It
must not merge, tag, release, delete branches, force push, or start M2.01.
Remote push/PR creation is a separate publication step unless explicitly
authorized by the campaign owner.
