# F5 — focused and native certification plan

Date: 2026-09-14

Status: **PASS WITH EXPLICIT NATIVE AND MATRIX DEFERMENTS**.

F5 is scoped from the actual candidate diff, not from milestone numbering.

## Candidate delta relevant to execution

Relative to the stabilization policy base, the candidate changes three
runtime/toolchain-relevant release surfaces:

1. `pyproject.toml`: distribution metadata `0.7.0 -> 1.0.0`;
2. `bootstrap/s3/wasm_target.py`: deterministic artifact identity default `s3-bootstrap-0.7.0 -> s3-bootstrap-1.0.0`.
3. `setup.py`: reproducible sdist archive timestamps and ownership when an
   explicit `SOURCE_DATE_EPOCH` is provided.

The remaining candidate changes are release tests, release CI, reports and release notes.

No parser, semantic analyzer, IR lowering, optimizer, emulator, native x86-64 backend, AArch64 backend, FFI implementation, TLS implementation, registry implementation, or self-host implementation is changed by the stable-candidate preparation itself.

## Focused impact gates

Before candidate freeze, obtain fresh execution evidence for at least:

```text
tests/test_release_version_surfaces.py
tests/test_m149_wasm_target.py
tests/test_ai_capabilities.py
tests/test_artifact_versioning.py
tests/test_source_syntax_defaults.py
```

The package and security workflows in F3/F4 provide their own focused execution gates.

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

The release campaign must obtain an actual executable run. Pre-step runner allocation failures do not count as either PASS or code FAIL.

## Native certification treatment

The candidate metadata/version change does not alter Linux x86-64 code generation, but stable publication must still retain current native evidence and obtain the required current-equivalent native gate when an execution environment is available.

Unsupported or structurally-only targets must remain classified factually. No AArch64/macOS/WASM structural evidence may be promoted to runtime certification for the stable release.

## T0–T3 / current-equivalent treatment

The repository has evolved beyond early milestone gate naming. For this release campaign, the current equivalent is defined operationally as:

1. focused version/WASM identity tests;
2. complete normal CI matrix applicable to the candidate;
3. package/install/security release gates;
4. native x86-64 required job;
5. only after those are green, candidate freeze and the separately authorized one-shot full-lineage T4.

This mapping preserves the intent of evidence escalation without inventing fake historical gate results.

## Execution evidence

```text
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
```

The five required focused modules passed (`57 passed`). F3 package smokes
and F4 security regressions provide the additional release-surface evidence.
The normal broad matrix was not rerun locally because the configured Actions
runner was unavailable, and Linux x86-64 native certification was not
promoted from this Windows host. The final T4 remains outside F5 and is not
authorized by this report.
