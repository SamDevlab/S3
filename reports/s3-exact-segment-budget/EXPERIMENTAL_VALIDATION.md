# Experimental Validation Status

## Provenance and isolation

Base source: `e07d0b5464bf472b2ca18993f3e196a234ff0fc5`.

The experiment lives on `experiment/s3-exact-segment-budget-backend` in an
isolated Windows worktree and its mirrored Linux VM worktree. The original
dirty Windows checkout was not modified. The default public native-assembly
function signature is unchanged.

Three frozen native-assembly outputs generated at the base SHA were compared
with this candidate's default mode. Their byte counts and SHA-256 values match:

| Corpus case | Bytes | SHA-256 |
| --- | ---: | --- |
| linear | 50066 | `a3de7a61c09cca2d3d8807aed3fe0f80025cb726215e69990d661c4ba8ec485d` |
| loop and calls | 100099 | `252d92b5f153d707691ca3367f49ec0feee89fbfb0aa1f216a343dd4c31b8b95` |
| bounds failure | 69723 | `3f6932ecf7bd67c4e2f378fa9e56e97f65e978b7cd3bc612272fb153c7a87b64` |

Classification: `DEFAULT_MODE_BYTE_STABILITY=PASS` for this frozen corpus.

## Current focused gates

- On the final candidate, the focused group
  `test_exact_segment_instruction_budget.py`,
  `test_register_init_native_safety.py`, `test_native_x86_64.py`, and
  `test_native_x86_64_integration.py` completed on Linux x86-64 with
  `S3_NATIVE_REQUIRED=1` and exit 0. It includes the regression for fused
  `TCMP/TBR3` with guarded register reads.
- The benchmark-side JSMN build-only preflight produced all eight P0/P1/P2/PNEG
  artifacts for O0/O1. Candidate P0 assembly matched the control in both
  optimization modes. This preflight performed no timing.
- `python -m compileall -q bootstrap/s3 tests`: passed on Linux at the final
  candidate.
- `git diff --check`: passed on the frozen source before this documentation-only
  update; it is rerun after the update.

## Frozen source validation

Final tested source SHA: `1a76e341098b54a639fec22eecea362cc243c46f`.

Exactly one complete S3 suite ran on the Linux x86-64 VM from a clean detached
worktree at that SHA, with `S3_NATIVE_REQUIRED=1`. It terminated with exit 0:
4,373 passed, 1 skipped, 0 failed, and 0 errors. The progress transcript
contains 4,374 collected outcomes, including one skip marker; the `-q` setting
is applied both by project configuration and the invocation, so pytest's final
count summary is suppressed. The immutable host transcript is
`%TEMP%/s3-full-suite-1a76e341-20260923.log` (SHA-256
`1b92f9a4009b7e8f50b91e5ab47fdba1a699acfc6ecdbb1a9af3a27a7f455d4e`), with
execution status in the adjacent `.status` file. The run started at
`2026-09-23T09:41:32-03:00`, ended at `2026-09-23T10:41:20-03:00`, and the
checkout remained clean at the tested SHA.

The candidate fixes missing diagnostic context in the exact-segment fused
`TCMP/TBR3` path: context is now established before guarded register reads,
including when fast-path accounting omits per-instruction instrumentation.
The new regression verifies the runtime guard and failure-site function, block,
and opcode. This was discovered by the JSMN build preflight before correctness
or timing; no benchmark timing was performed for that failed attempt.

E0 equivalence remains scoped to serialized execution, including synchronous
callback re-entry at a call barrier; concurrent FFI entry is not qualified. No
performance result is claimed here. The independent S3-Benchmarks campaign has
not yet measured this source SHA.

Only documentation may change after the frozen source gates. Any subsequent
source, test, or executable-logic change invalidates the full-suite gate and
requires a new tested source SHA and one new full-suite run.
