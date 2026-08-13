# P8.1 local evidence reconciliation

## Status

```text
P8_LOCAL_CAMPAIGN_STATUS=COMPLETE_NO_VALID_TARGET_YET
P8_SELECTION=NO_VALID_TARGET_YET
P8_STARTED=NO
P8_IMPLEMENTED=NO
P9_STARTED=NO
PRODUCTION_COMPILER_CHANGED=NO
```

All compiler evidence for this campaign was produced locally. GitHub Actions
were intentionally not triggered because the account's included allowance is
exhausted. The workflow audit found that non-main feature/research pushes do
not match a `push` workflow, while PR creation and main pushes do match one or
both workflows. No PR, main push, merge, rerun or dispatch was performed.

The exact production target was `631b51e70562a33183ac14d0be5bbe2ddd140779`.
The laboratory structural validator and production-provenance validator both
passed, and the detached Linux checkout matched the target SHA.

The post-P7 12-workload profile passed emulator and Linux native execution for
all workloads. The first-useful-work probe passed nine tiny workloads with
matching emulator/native outputs. These are baseline and causal-triage
evidence, not an implementation result.

The remaining large native cost is concentrated in representation/lowering
expansion, especially initialization-state and checked memory/control
materialization. Those events have concrete failure, memory-validity,
instruction-limit, ABI or successor-observer witnesses. A path-complete proof
of removable state is absent, so the broad candidates were falsified for
promotion. A future campaign may revisit them only with stronger attribution.

No local P8 production candidate exists. Consequently the exact-candidate
Linux full suite and candidate-before/after measurements were not run; running
them without a coherent candidate would violate the campaign's test-economy
rule. The remote PR/CI/merge step remains deferred until Actions are available
or a human authorizes the remote gate.

```text
LAB_CONSISTENCY_FINAL=PASS
PROVENANCE_RECORDED_FINAL=YES
ORIGINAL_CHECKOUT_PRESERVED=YES
GITHUB_ACTIONS_RUNS_TRIGGERED=0
SHUTDOWN_AUTHORIZED=NO
SHUTDOWN_EXECUTED=NO
```
