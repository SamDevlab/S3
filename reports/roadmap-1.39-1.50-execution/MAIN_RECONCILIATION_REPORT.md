# M1.39-M1.50 Main Reconciliation

## Scope

This report records a local-only integration of the autonomous closure into a
new branch based on `origin/main`. The primary checkout and autonomous closure
worktree were not modified. No push, PR, remote merge, tag, release, or
shutdown action was performed.

## Topology

```text
ORIGIN_MAIN_SHA=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
AUTONOMOUS_CLOSURE_SHA=4d670528a2f9e3f78fe99caa147fcd27231014a2
COMMON_BASE=48ad3ab70c179abc1eb942e78780b8cad6338509
INTEGRATION_MERGE_COMMIT=208db9df9466673e0cc89c111ba13ca3654bcb3a
INTEGRATION_BRANCH=integration/m139-m150-main-reconciliation-20260817
```

The normal non-fast-forward merge preserved both parents. There were nine
content conflicts: `emitter.py`, `layout.py`, `cli.py`, `dynamic.py`,
`emulator.py`, `host_services.py`, `semantic.py`, and `verifier.py` (with
three separate emitter hunks). They were resolved by semantic ownership:
main-line numeric/native behavior was retained, and the M1.39-M1.50 typed
dynamic, resource, test-runner, and target additions were retained. No
unresolved conflict remains.

The 86 main-only commits and 54 autonomous-only commits remain ancestors of
the integration branch; neither history was replaced or rebased.

## Evidence Backfill

Historical implementation SHAs for M1.39-M1.44 are known, but exact historical
`tested_sha` values are absent from all persisted ledgers and preserved status
artifacts. They remain `null`; no SHA was guessed. Their contracts are instead
certified against the integrated tree with:

```text
CERTIFICATION_MODE=RETROACTIVE_FINAL_TREE_CERTIFICATION
CERTIFICATION_SHA=efcbd464c091508fd975a6a647ba8bc023a7db21
```

The integrated focused batch passed with exit 0:

```text
python -m pytest -q tests/test_m139_dynamic_buffers.py tests/test_m140_ordered_collections.py tests/test_m141_ordered_maps_sets.py tests/test_m142_structured_results.py tests/test_m143_scoped_resources.py tests/test_m144_standard_library.py tests/test_m145_build_graph.py tests/test_m146_test_runner.py tests/test_m147_python_buffer_abi.py tests/test_m148_network_provider.py tests/test_m149_wasm_target.py tests/test_m150_renderer_component.py
INTEGRATED_FOCUSED_EXIT=0
```

The integrated O1 renderer gate initially exposed a non-terminal dominance
cost on the Windows host. A bounded, semantics-preserving reverse-postorder
convergence repair was made in `bootstrap/s3/dominance.py`; the dominance/GVN
regression tests passed, and the focused batch then completed successfully.

M1.50 historical closure metadata now records:

```text
M150_HISTORICAL_CLOSURE_SHA=4d670528a2f9e3f78fe99caa147fcd27231014a2
```

Environment-only certification remains explicitly deferred for M147-L,
M148-L, M149-W, and M150-W. The accepted M1.50 observable-memory O1 parity
deferment is unchanged. No goldens were changed.

## Final Suite

The canonical final full suite is required after this evidence commit. Its
command and exact certification SHA will be recorded in the final closure
amendment; no parallel suite is permitted.

```text
FINAL_PUBLICATION_FULL_SUITE_EXIT=PENDING
```

## Readiness Before Final Suite

```text
MERGE_CONFLICT_COUNT=9
MERGE_CONFLICTS_RESOLVED=YES
MAIN_ONLY_COMMITS_PRESERVED=YES
AUTONOMOUS_ONLY_COMMITS_PRESERVED=YES
UNEXPECTED_FILES=TO_BE_VALIDATED
SECRET_FINDINGS=TO_BE_VALIDATED
READY_TO_PUBLISH=PENDING_FINAL_FULL_SUITE
REMOTE_WRITE_EXECUTED=NO
```
