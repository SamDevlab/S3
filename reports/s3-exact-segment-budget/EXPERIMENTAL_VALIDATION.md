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
  implementation before the final diagnostic-helper micro-adjustment; focused
  tests and `py_compile` passed after that adjustment. Final compileall remains
  a source-freeze gate.
- `git diff --check`: passed before report authoring; final check remains
  pending.

## Pending; do not infer

At the time of this snapshot, the one full S3 suite at source freeze has not
run, the source SHA has not been frozen, and S3-Benchmarks has not consumed a
candidate SHA. No performance result is claimed. Linux native E0 evidence is
scoped to serial execution; concurrent FFI entry is not qualified.
