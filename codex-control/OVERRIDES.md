# Live overrides

CONTROL_REVISION: 2

No emergency stop is active.

Current direction:

- Stage 01 is treated as completed from Codex's reported checkpoint. Active work is Stage 02 hosted contract qualification.
- The Stage 02 import failure is a **handoff dependency-closure issue**, not a semantic test failure.
- Before interpreting any hosted test result, read `codex-control/HANDOFF_IMPORT_MANIFEST.json` and make the selective checkout contain the exact required v2 closure.
- The two newly identified direct dependencies are:
  - `tools/stage1_semantic_ir_reference.py`
  - `tools/stage1_source_binding_reference.py`
- `tools/stage1_semantic_stream_v2.py` imports both of those. `tools/verify_stage1_semantic_conformance_v2.py` imports `tools.stage1_semantic_stream_v2`.
- Do not solve this by merging PR #270. Import/copy only the files listed in the manifest from `origin/parallel/pr268-semantic-lowering-v1-20260827`.
- After importing, verify each imported file against the blob SHA recorded in the manifest before rerunning compileall/pytest.
- If another missing `tools.*` dependency appears, stop the repeated trial-and-error loop and first compute/inspect the import graph from the imported Python files. Add only dependencies that originate from the handoff branch; existing `bootstrap/s3/*` modules should come from the implementation checkout.
- Treat S3IR2 v2 as frozen. Do not redesign the protocol to avoid an import problem.
- Work on candidate transforms/artifacts first; canonical `selfhost/compiler/s3c_stage1.s3` remains unauthorized for mutation.
- Local Linux x86-64 evidence remains authoritative while GitHub Actions fails before exposing job steps.
- SELF_EMIT, Stage2, Stage3 and T4 remain unauthorized.

Required Stage 02 evidence after dependency repair:

```text
CONTROL_REVISION=2
HANDOFF_IMPORT_CLOSURE=PASS
IMPORTED_BLOB_SHAS=PASS
PYTHON_COMPILEALL=PASS/BLOCKED
V2_FOCUSED_PYTEST=PASS/BLOCKED
S3_V2_PRIMITIVES_CHECK=PASS/BLOCKED
V2_CONTRACT_JSON=PASS/BLOCKED
```

A failure after the import closure is correct may be classified as a real hosted test/code failure. A failure caused by an absent handoff module is `IMPORT_CLOSURE_BLOCKED`, not `TEST_FAIL`.

If the control-branch fetch/read fails, Codex may finish the current atomic command but must not enter a new stage, create an implementation commit, mutate canonical Stage1 or cross a promotion/bootstrap gate until the live control revision can be read again.
