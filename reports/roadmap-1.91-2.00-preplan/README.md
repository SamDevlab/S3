# M1.91-M2.00 Provisional Pre-Plan

This document is a planning checkpoint only. It does not authorize runtime
implementation, a branch, a pull request, a merge, or benchmark publication.
The repository contains no substantive pre-existing M1.91-M2.00 roadmap; the
only earlier reference records that M1.91 had not started. This provisional
sequence is therefore preserved as a new planning artifact.

## Proposed sequence

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
parallel after M1.92, while M1.94 and M1.96 consume their respective outputs.
M1.97, M1.98, M1.99, and M2.00 remain ordered release gates.

## Status lock

`M191_M200_IMPLEMENTATION_STARTED=NO`

The M1.81-M1.90 publication campaign is not merged into the canonical main
line by this pre-plan. Entry criteria and promotion rules are defined in the
companion files and must be satisfied before any implementation campaign.
