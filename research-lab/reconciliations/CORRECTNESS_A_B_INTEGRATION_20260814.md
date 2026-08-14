# Correctness Candidate A+B Integration Reconciliation

## Candidate Genealogy

```text
CORRECTNESS_BASE_MAIN=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
CORRECTION_A=f71eb2dad070a9a71fe8d9dec1dfbcdd7589b252
CORRECTION_B=045bbb1427af941b71d28b93cf1e5fe9bf245af7
STACK_ORDER=MAIN -> A -> B
FULL_SUITE_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
FULL_SUITE=PASS
NATIVE=PASS
DIFFERENTIAL=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
WORKTREE_CLEAN=YES
```

The candidate is correct and reproducible, but it is not main. A introduced
structural `InstructionSite` identity; B selected `ALWAYS_MATERIALIZE_TMOV`.
The exact candidate Linux full suite exited 0. The P9 sidecar's `+12` model
delta is correctness-only and is not counted as an optimization.

## Static Integration-Route Analysis

No integration alternative was executed. The following results come from the
workflow trigger and provenance model for the exact candidate, current main,
and production/test paths:

| EVENT | TARGET_REF | CHANGED_PATHS | WORKFLOW_PROVENANCE | TRIGGER_RESULT | CLASSIFICATION |
| --- | --- | --- | --- | --- | --- |
| `push` | `fix/native-tmov-copy-semantics-20260814` | production + tests | no matching workflow | 0 possible runs | `PROVEN_ZERO_ACTIONS` |
| `pull_request` | feature ref | production + tests | merge/ref semantics outside bounded model | unknown | `UNKNOWN` |
| `push` | `main` | production + tests | `tests.yml`, `m138-docker.yml` match | 2 possible runs | `ACTIONS_POSSIBLE` |
| `workflow_dispatch` | feature ref | production + tests | no matching manually dispatchable workflow | 0 possible runs | `PROVEN_ZERO_ACTIONS` |

The feature-branch push is safe as a publication event, but it does not
integrate main. A real PR merge necessarily includes the unresolved
`pull_request` semantics and the resulting main-ref update is
`ACTIONS_POSSIBLE`. A direct main-ref update is also `ACTIONS_POSSIBLE` and is
not an allowed workaround. `workflow_dispatch` is not an integration route
for these workflows.

Therefore:

```text
CORRECTNESS_CANDIDATE_VALIDATED=YES
CURRENT_MAIN_MATCHES_EXPECTED_BASE_OR_REVALIDATED=YES
INTEGRATION_EVENT_PROVENANCE=NOT_PROVEN_ZERO_ACTIONS
CORRECTNESS_INTEGRATION=BLOCKED
CORRECTNESS_INTEGRATED=NO
PR_CREATED=NO
MAIN_UPDATED=NO
```

No workflow was modified, no skip marker was added, no PR was opened, and no
remote action was triggered.
