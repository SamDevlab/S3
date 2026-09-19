# PR #301 Validation Plan

This plan is intentionally deferred to the user's validation round. No command
in this file is evidence until its actual output is captured.

## Candidate provenance

```text
BASE_MAIN_SHA=4c7aaf4ad59fdacdd83f230e11a0bd979081c80a
IMPLEMENTATION_SOURCE_HEAD=e6b9122eb446d0f543e1d701b11219e22ecb85bb
SOURCE_CHANGED_AFTER_IMPLEMENTATION_HEAD=NO
PR=301
```

If source/test code changes after this plan is written, update
`IMPLEMENTATION_SOURCE_HEAD` before treating results as certification.

## T0 — static Python/repository checks

Run once:

```text
python -m compileall -q bootstrap tools tests
git diff --check
```

Expected gate:

```text
COMPILEALL=PASS
DIFF_CHECK=PASS
```

## T1 — focused frontend/control-plane suite

Run:

```text
python -m pytest -q \
  tests/test_source_frontend.py \
  tests/test_frontend_registration.py \
  tests/test_frontend_control_plane.py \
  tests/test_whole_program_composition.py \
  tests/test_generic_syntax_ir_verifier.py
```

This tier is expected to exercise:

- reference-vs-independent lexer parity;
- reference-vs-independent parser logical parity;
- no reference lexer/parser callback in the independent path;
- SyntaxArena parser-level payload changes;
- source bundle / shared symbol behavior;
- source syntax -> ProgramRegistry projection;
- implicit module identity;
- import visibility and cycle rejection;
- per-nominal field/variant ranges;
- frontend phase ingestion through REGISTRATION;
- `compile_program` real-source ingestion and fail-closed TYPE boundary;
- import visibility, module-cycle validation, and type-import-alias rejection in ProgramRegistry;
- function generic-arity and unresolved nominal type-syntax retention;
- existing whole-program transaction/orchestration regressions.

Do not proceed to full-suite certification if this tier has unresolved
feature-caused failures.

## T2 — broader adjacent regressions

Recommended before a full suite:

```text
python -m pytest -q \
  tests/test_module_graph.py \
  tests/test_modules_pipeline.py \
  tests/test_s3_compound_assignment_parser.py
```

If repository test selection has changed, preserve the exact node IDs actually
run.

## T3 — full Windows

After focused closure, run exactly one full Windows suite:

```text
python -m pytest -q
```

Capture selected/passed/skipped/failed/errors/exit code.

Do not rerun blindly on failure. Preserve failing node IDs and classify them.

## T4 — Linux / native frontend qualification

The current branch includes ordinary-S3 token, lexer-state, and parser-state
shapes, but it does not claim complete native frontend execution.

For this PR, Linux should at minimum run the focused Python frontend/control
plane set and the repository's existing native regression gates. If a complete
ordinary-S3 lexer/parser implementation is added later, that requires a
separate explicit native differential matrix and should not be inferred from
the current state-shape probes.

## CI infrastructure

If GitHub Actions jobs continue to show no steps / no runner execution, record:

```text
CI_STATE=INFRASTRUCTURE_BLOCKED_PRE_EXECUTION
```

No workflow weakening and no repeated rerun loop.

## Merge readiness

Do not mark Ready for Review until all implemented source changes have focused
evidence and full-suite closure appropriate to their blast radius.

Current expected state before validation:

```text
READY_FOR_USER_TEST_ROUND=YES
READY_FOR_MAIN_MERGE=NO_VALIDATION_PENDING
SELFHOST_REENTRY_AUTHORIZED=NO
STAGE1_V4=NOT_AUTHORIZED
SHUTDOWN_SCHEDULED=NO
SHUTDOWN_EXECUTED=NO
```