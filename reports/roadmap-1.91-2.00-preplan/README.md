# M1.91-M2.00 Campaign Pre-Plan

This directory defines the planning contract for the M1.91-M2.00 line.
The predecessor line M1.81-M1.90 is now merged into canonical `main` through
PR #183 at merge commit `a9e430551f2ee77aa2ef229daf9e967333e83e2c`.

A campaign base branch has been prepared from that exact canonical commit:

`feature/m191-m200-autonomous-20260819`

Preparing the branch and documentation does **not** start M1.91 implementation.
No source/runtime change, pull request, merge, tag, release, or benchmark
publication is authorized by this base preparation alone.

## Planned sequence

| Milestone | Capability focus |
|---|---|
| M1.91 | async control flow and deterministic select |
| M1.92 | synchronization primitives |
| M1.93 | streaming HTTP and server boundaries |
| M1.94 | TLS server and secure channels |
| M1.95 | package resolution and registry v2 |
| M1.96 | signed indexes and trust policy |
| M1.97 | AArch64 native object and link integration |
| M1.98 | cross-platform backend parity |
| M1.99 | benchmark-driven runtime and codegen optimization |
| M2.00 | release candidate and language stability gate |

M1.91-M1.92 are ordered prerequisites. M1.93 and M1.95 may be researched in
parallel after M1.92, but implementation remains sequential inside the campaign
unless the campaign contract explicitly records otherwise. M1.94 and M1.96
consume their respective predecessor outputs. M1.97, M1.98, M1.99, and M2.00
remain ordered release gates.

The executable campaign rules live in:

- `reports/roadmap-1.91-2.00-execution/CAMPAIGN_BASELINE.md`
- `reports/roadmap-1.91-2.00-execution/CAMPAIGN_CONTRACT.md`
- `reports/roadmap-1.91-2.00-execution/HANDOFF_STATE.md`

## Status lock

```text
M181_M190_MERGED=YES
M181_M190_MERGE_SHA=a9e430551f2ee77aa2ef229daf9e967333e83e2c
M191_M200_BASE_BRANCH=feature/m191-m200-autonomous-20260819
M191_M200_BASE_PREPARED=YES
M191_M200_IMPLEMENTATION_STARTED=NO
M191_STARTED=NO
```
