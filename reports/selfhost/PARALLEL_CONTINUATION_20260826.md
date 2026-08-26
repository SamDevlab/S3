# PR #268 parallel continuation — 2026-08-26

Branch: `audit/pr268-parallel-stage1-certification-20260825`

Checkpoint HEAD before this document: `06d0308242261a1846502a484dd7fafd3c400fe3`

This continuation was prepared while the main autonomous agent was still working locally on the PR #268 worktree. **Do not merge or cherry-pick into the PR while that agent is still mutating its local candidate.** Reconcile only after a terminal checkpoint/push from the main agent.

## Main-agent context observed externally

The latest supplied status showed:

- the Linux guest remained healthy;
- the initialization-analysis OOM was addressed with a compact bitset-oriented internal representation plus validation-only/no-detailed-report call paths;
- focused initialization tests passed before the next native attempt;
- the expanded candidate compiled without the previous OOM;
- the first semantic regression in the incremental capacity matrix was isolated to the event-writer stage;
- root cause: generated dispatch treated boolean `<` as if its result were ordered `-1/0/+1`;
- corrected relation-safe dispatch was being revalidated on the stage-04 event writer;
- Stage2/Stage3/T4 were still not started.

This branch does not claim those local-agent changes as repository evidence. They are context for parallel review only.

## New parallel protection 1 — relation-safe bank dispatch

Added:

- `reports/selfhost/stage1/capacity-dispatch-proof-contract.json`
- `tools/stage1_relation_dispatch.py`
- `tools/audit_stage1_relation_dispatch.py`
- `tests/test_stage1_relation_dispatch.py`

Contract:

```text
== != < <= > >=
    boolean trit predicate
    true  = -1
    false = 0
    +1    = impossible/fail-closed

<=>
    ordered three-way relation
    less    = -1
    equal   = 0
    greater = +1
```

Safe generated boolean partition:

```text
selector == pivot
    -1 -> pivot
     0 -> evaluate selector < pivot
     1 -> FAIL CLOSED

selector < pivot
    -1 -> left subtree
     0 -> right subtree
     1 -> FAIL CLOSED
```

The shared helper validates sorted unique bank keys, routes invalid selectors closed, and has an exhaustive Python oracle.

The hosted audit also generates an S3 route for 11 banks. Its aggregate correctness check deliberately **does not** use ternary `&`; instead it converts each predicate to i64, sums all `-1` true values, and requires the exact negative predicate count. This prevents a false-positive aggregate proof.

No native PASS is claimed.

## New parallel protection 2 — initialization-analysis scalability contract

Added:

- `reports/selfhost/stage1/initialization-analysis-scalability-contract.json`
- `tools/audit_stage1_initialization_scalability.py`
- `tests/test_stage1_initialization_scalability.py`

The current repository baseline uses a dense map keyed by `(memory_id,index)` and persists full entry/exit state per reachable block. The parallel contract records that the scalable implementation may use two bitsets or equivalent packed tri-state storage only if it preserves:

- the same definite-uninitialized LOAD error;
- the same immutable double-write error;
- the same unknown-index STORE semantics;
- the same CFG joins;
- the same unreachable-block behavior;
- `verify_ir` before analysis;
- identical validation behavior whether or not a detailed `InitializationReport` is materialized.

The audit reports logical dense-entry pressure and a two-bitset word projection. It explicitly does **not** label that projection as RSS/runtime measurement.

No native PASS is claimed.

## New parallel protection 3 — banked storage roundtrip

Added:

- `reports/selfhost/stage1/banked-storage-roundtrip-contract.json`
- `tools/audit_stage1_banked_storage_roundtrip.py`
- `tests/test_stage1_banked_storage_roundtrip.py`

Required invariant:

```text
logical index
    -> exactly one (bank,slot)
    -> write one slot
    -> read same index
    -> exact same full-width value
```

The audit exhaustively models these layouts:

```text
instruction:   [365,365]
value:         [365,365,365,365]
call args:     [365,365,16]
event example: 11 x 365
```

Important call-argument boundaries are pinned explicitly:

```text
364 = last bank-0 slot
365 = first bank-1 slot
729 = last bank-1 slot
730 = first tail-bank slot
745 = last valid slot
746 = invalid
```

It also injects signed-i64 extreme payloads on boundary slots, requires exactly one physical slot to change per boundary write, and verifies invalid accesses do not mutate storage.

This model is necessary but not native evidence. The exact transformed writer/reader still has to pass native trivial/self-source/audit gates.

## Parallel branch policy

Do not integrate blindly.

After the main agent reaches a checkpoint:

1. fetch its final PR/local-pushed HEAD;
2. inspect the actual `_eq_chain`/capacity writer/readers and initialization patch;
3. keep main-agent code if it is stronger or already equivalent;
4. bring over only missing contracts/oracles/tests;
5. adapt exact bank counts to measured native requirements;
6. run focused hosted tests;
7. run native Linux qualification once prerequisites authorize it;
8. keep Stage2 blocked until the Stage1 certification gate is real.

## Current parallel status

```text
PARALLEL_BRANCH_ONLY=YES
MAIN_PR_MUTATED_BY_PARALLEL=NO
CANONICAL_STAGE1_SOURCE_MUTATED=NO

RELATION_DISPATCH_GATE=PREPARED_NOT_EXECUTED_HERE
INITIALIZATION_SCALABILITY_GATE=PREPARED_NOT_EXECUTED_HERE
BANKED_ROUNDTRIP_GATE=PREPARED_NOT_EXECUTED_HERE

NATIVE_EVIDENCE_FROM_NEW_PARALLEL_WORK=NO
STAGE1_CERTIFIED_FOR_STAGE2=NO
STAGE2_STARTED=NO
STAGE3_STARTED=NO
FULL_SELF_HOSTING=NO
```
