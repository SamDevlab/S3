# P8.1 Actions trigger incident

The initial audit inspected the workflows in the exact production checkout at
`631b51e70562a33183ac14d0be5bbe2ddd140779`. That checkout had a `tests.yml`
push filter restricted to `main`. The research branch used for persistence had
a different `tests.yml` definition at its pushed head:

```yaml
on:
  push:
  pull_request:
```

The research push of `06ed79449dcd917c3213570389a3639f6ad0be24` therefore
triggered the `Tests` workflow as `run 31748403817`. All jobs failed within two
seconds with no step logs, consistent with the exhausted Actions allowance.

This is an `ACTIONS_TRIGGER_RISK` caused by auditing the target production
workflow instead of the workflow definitions present on the branch to be
pushed. No rerun, retry, cancellation, PR, main write or further remote write
was performed after discovery. The research branch is now treated as unsafe
to push under the current repository state.

```text
GITHUB_ACTIONS_RUNS_TRIGGERED=1
PUSH_RESEARCH_BRANCH_SAFE=NO
REMOTE_WRITES_AFTER_DISCOVERY=0
```
