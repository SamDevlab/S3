# F5 — focused and native certification plan

Date: 2026-09-14

Status: **PASS WITH EXPLICIT NATIVE AND MATRIX DEFERMENTS**.

F5 is scoped from the actual candidate diff, not from milestone numbering.

## Candidate delta relevant to execution

Relative to the stabilization policy base, the candidate changes three runtime/toolchain-relevant release surfaces:

1. `pyproject.toml`: distribution metadata `0.7.0 -> 1.0.0`;
2. `bootstrap/s3/wasm_target.py`: deterministic artifact identity default `s3-bootstrap-0.7.0 -> s3-bootstrap-1.0.0`;
3. `setup.py`: reproducible sdist archive timestamps and ownership when an explicit `SOURCE_DATE_EPOCH` is provided.

The remaining candidate changes are release tests, release CI, reports and release notes.

No parser, semantic analyzer, IR lowering, optimizer, emulator, native x86-64 backend, AArch64 backend, FFI implementation, TLS implementation, registry implementation, or self-host implementation is changed by the stable-candidate preparation itself.

## Focused impact gates

Fresh execution evidence was obtained for:

```text
tests/test_release_version_surfaces.py
tests/test_m149_wasm_target.py
tests/test_ai_capabilities.py
tests/test_artifact_versioning.py
tests/test_source_syntax_defaults.py
```

Result: `57 passed`, exit `0`.

The package and security gates in F3/F4 provide additional release-surface evidence.

## Normal compiler matrix

The existing `.github/workflows/tests.yml` remains the primary broad current-equivalent gate. It covers:

- supported Python 3.11/3.12/3.13 unit groups;
- renderer/adapter/fixture-output group;
- benchmark group;
- SSA per-pass verification;
- deterministic differential generation;
- numeric-domain closure;
- required Linux x86-64 native integration;
- benchmark smoke.

The current GitHub-hosted attempt did not obtain a runner and therefore produced no executable result. This is a deferment, not PASS and not source FAIL.

## Native certification treatment

The candidate metadata/version/reproducible-sdist changes do not alter Linux x86-64 code generation. The local certification host is Windows 11 AMD64 and does not provide the Linux x86-64 toolchain required by the native job.

Therefore:

```text
F5_LINUX_X86_64_NATIVE_CERTIFICATION=DEFERRED_ENVIRONMENT_UNAVAILABLE
```

This deferment must be reconciled explicitly before F6 freeze. The preferred path is fresh executable Linux/current-matrix evidence. Reuse of earlier RC2 evidence is permitted only if a separate documented release-impact decision explicitly accepts it; it must never be silently reclassified as a fresh PASS.

Unsupported or structurally-only targets remain classified factually. No AArch64/macOS/WASM structural evidence is promoted to runtime certification for the stable release.

## T0–T3 / current-equivalent treatment

The repository has evolved beyond early milestone gate naming. For this release campaign, the current equivalent is defined operationally as:

1. focused version/WASM identity tests;
2. complete normal CI matrix applicable to the candidate, or an explicitly accepted impact-policy substitution/deferment;
3. package/install/security release gates;
4. native x86-64 required job when executable, or an explicitly accepted impact-policy deferment;
5. only after those are reconciled, candidate freeze and the separately authorized one-shot full-lineage T4.

This mapping preserves the intent of evidence escalation without inventing fake historical gate results.

## Execution evidence

```text
LOCAL_CERTIFIED_SOURCE_HEAD=779f6ddb0a5a2e55ea57a3c6e07749f150d83455
F5_IMPACT_MAP=PASS
F5_FOCUSED_TEST_SELECTION=PASS
F5_NORMAL_MATRIX=DEFINED
F5_NATIVE_X86_64_GATE=DEFINED
F5_UNSUPPORTED_TARGET_POLICY=PRESERVED
F5_EXECUTABLE_FOCUSED_RESULT=57_PASSED
F5_EXECUTABLE_NORMAL_MATRIX_RESULT=DEFERRED_CI_RUNNER_UNAVAILABLE
F5_EXECUTABLE_NATIVE_RESULT=DEFERRED_ENVIRONMENT_UNAVAILABLE
F5_HOST_INDEPENDENT_GATES=PASS
F5_LINUX_X86_64_NATIVE_CERTIFICATION=DEFERRED_ENVIRONMENT_UNAVAILABLE
F5_OS=Windows-11
F5_ARCHITECTURE=AMD64
F5_TOOLCHAIN=gcc:ABSENT,clang:ABSENT,ld:ABSENT
F5_STATUS=PASS_WITH_EXPLICIT_NATIVE_AND_MATRIX_DEFERMENTS
F5_READY_FOR_F6_FREEZE=NO_PENDING_DEFERMENT_RECONCILIATION
```

The five required focused modules passed (`57 passed`). F3 package smokes and F4 security regressions provide the additional release-surface evidence. The final T4 remains outside F5 and is not authorized by this report.
