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

- New exact-segment structural and Linux native E0 module: 22 passed on the
  Linux x86-64 VM with `S3_NATIVE_REQUIRED=1`.
- Focused instruction-limit, native x86-64, native integration, FFI,
  registry/routing, Assembly verifier/control-flow, optimizer, and compilation
  context group: terminal exit 0 on the Linux VM.
- Same focused group on Windows: terminal exit 0; platform-native cases were
  skipped there and run on Linux instead.
- `python -m compileall -q bootstrap/s3`: passed on Windows for the current
  implementation after the final diagnostic-helper adjustment.
- `git diff --check`: passed before this documentation-only update; rerun after
  the update.

## Frozen source validation

Final tested source SHA: `f4353c1b5bc3557dd05188d893f85de264300d5f`.

Exactly one complete S3 suite ran on the Linux x86-64 VM from a clean detached
worktree at that SHA, with `S3_NATIVE_REQUIRED=1`. It terminated with exit 0:
4,372 passed, 1 skipped, 0 failed, and 0 errors. The immutable transcript is
`/home/vboxuser/tmp/s3-full-suite-f4353c1b-20260923.log` and records both the
tested SHA and `FULL_SUITE_EXIT=0`. The checkout remained clean at the tested
SHA after the run.

The focused Linux x86-64 E0 module separately passed all 22 tests. The complete
suite also ran with native validation required. E0 equivalence remains scoped
to serialized execution, including synchronous callback re-entry at a call
barrier; concurrent FFI entry is not qualified. No performance result is
claimed here. S3-Benchmarks validation has not yet consumed this candidate SHA.

Only this validation report may change after the frozen source gates. Any
subsequent source, test, or executable-logic change invalidates the full-suite
gate and requires a new tested source SHA and one new full-suite run.
