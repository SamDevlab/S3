# T4 Failure Triage

Historical T4 transcripts remain unchanged. The authorized final T4 was run
once at the post-reboot candidate; no timeout was rerun individually.

## Provenance

```text
HEAD=a651e9b3551f218af1c27bb908e0692880afc4da
BRANCH=feature/m191-m200-autonomous-20260819
ORIGIN_MAIN=a9e430551f2ee77aa2ef229daf9e967333e83e2c
WORKTREE_CLEAN_BEFORE_T4=YES
LOCAL_REMOTE_ALIGNED_BEFORE_T4=YES
SOURCE_TEST_RUNNER_MUTATION_BEFORE_T4=NO
```

## Final T4 result

```text
T4_RUNS_THIS_PROMPT=1
FINAL_T4_START=2026-08-21T05:42:08.6894598-03:00
FINAL_T4_END=2026-08-21T07:02:13.1286556-03:00
FINAL_T4_HEAD=a651e9b3551f218af1c27bb908e0692880afc4da
SELECTED=369
PASS=365
FAIL=0
TIMEOUT=4
UNCLASSIFIED_TIMEOUT=0
EXIT=1
STATUS=TIMEOUT
```

Every timeout row from the preserved JSON report:

```text
PATH=tests/test_assembly_renderer_candidate_readiness.py CLASS=HEAVY_RENDERER APPLIED_SECONDS=300
PATH=tests/test_compare_assembly_renderer.py CLASS=HEAVY_RENDERER APPLIED_SECONDS=300
PATH=tests/test_m150_renderer_component.py CLASS=HEAVY_RENDERER APPLIED_SECONDS=300
PATH=tests/test_s3_renderer_sign_text.py CLASS=HEAVY_RENDERER APPLIED_SECONDS=300
```

There are no failed files and no unclassified timeout rows. The gate is still
blocked because the four explicit timeout results are not successful test
results:

```text
M2_00_T4=BLOCKED
BLOCKER=1
READY_FOR_PR=NO
READY_FOR_MERGE_REVIEW=NO
```

No individual timeout rerun, benchmark, merge, tag, release, force push, or
M2.01 was performed.
