# Live overrides

CONTROL_REVISION: 3

No emergency stop is active.

Current direction:

- Stage 01 is complete.
- Stage 02 hosted contract qualification is now recorded as PASS from Codex's checkpoint: Python compilation, five hosted v2 tests, S3 primitive `cli check`, and contract JSON validation all passed after importing the exact dependency closure.
- Active work is Stage 03: candidate-only Pass 1 for functions, signatures, parameters, locals, loop variables, lexical scopes, mutability, and call-resolution metadata.
- Do not revisit Stage 02 unless a Stage 03 failure demonstrates an actual hosted-contract regression or imported file corruption.
- Do not repeat SSH/PR/health checks unless a concrete command fails for infrastructure reasons.
- The Stage 03 implementation must remain candidate-first. `selfhost/compiler/s3c_stage1.s3` canonical mutation remains unauthorized.
- Preferred implementation artifact remains `tools/patch_stage1_semantic_port_v2.py` producing `.artifacts/s3c_stage1_semantic_v2.s3`.
- Reuse proven v1 parser hooks only as implementation evidence; all emitted semantics and gates target S3IR2 v2.
- Function IDs, parameter IDs, local binding IDs, and storage slots must remain conceptually separate where appropriate. Semantic identity must not be defined by reusable physical scratch position.
- Preserve exact source name spans for functions/parameters/locals in the canonical ASCII self-hosting subset.
- Lexical shadowing must be explicit and fail closed on ambiguous lookup.
- Do not over-expand fixed arrays speculatively. Measure the actual candidate peak before changing bounded scratch capacity.
- Stage 03 is allowed to finish with aggregate `S1=PARTIAL_EXPECTED`; constants and instruction results are intentionally Stage 04.
- Before any Stage 03 implementation commit, re-fetch this control branch and report `CONTROL_REVISION=3` unless a newer revision appears.
- SELF_EMIT, Stage2, Stage3 and T4 remain unauthorized.

Required Stage 03 evidence:

```text
CONTROL_REVISION=3
PASS1_FUNCTIONS=PASS/BLOCKED
PASS1_SIGNATURES=PASS/BLOCKED
PASS1_PARAMETERS=PASS/BLOCKED
PASS1_LOCALS=PASS/BLOCKED
PASS1_LOOP_BINDINGS=PASS/BLOCKED
PASS1_SCOPE_RESOLUTION=PASS/BLOCKED
PASS1_SHADOWING=PASS/BLOCKED
CANDIDATE_STAGE0_CHECK=PASS/BLOCKED
CANONICAL_SOURCE_MUTATED=NO
S1=PARTIAL_EXPECTED/BLOCKED
FIRST_REAL_BLOCKER=
```

If a Pass1 gate fails because implementation is missing, continue implementing that slice. Do not advance merely to report the blocker.

If the control-branch fetch/read fails, Codex may finish the current atomic command but must not enter a new stage, create an implementation commit, mutate canonical Stage1 or cross a promotion/bootstrap gate until the live control revision can be read again.
