# S3 1.2 Whole-Program Composition Foundation

## Scope and boundary

This increment adds the whole-program compiler control plane around prepared
syntax and IR artifacts. It does not implement a lexer, parser, expression
semantic analyzer, generic lowerer, optimizer, emitter, source-to-output
compiler, Stage1 V4, Stage2, Stage3, release, tag, or shutdown.

```text
BASE_MAIN_SHA=ecda016e2bbca4be43e939c8a674c62e7db8e185
FINAL_TESTED_SOURCE_HEAD=e4d7aa5492e597da8f730671727f8bd5c66180d2
SOURCE_CHANGED_AFTER_FINAL_GATES=NO
PR_MERGED=NO
RELEASE=NO
TAG=NO
PYPI=NO
SHUTDOWN_SCHEDULED=NO
SHUTDOWN_EXECUTED=NO
SELFHOST_REENTRY_AUTHORIZED=NO
STAGE1_V4=NOT_AUTHORIZED
STAGE1_V4_STARTED=NO
```

## Control plane

- `ProgramId` is one explicit root per `WholeProgramContext`.
- Module, function, nominal-type, import, and export identities are direct,
  deterministic arena IDs with explicit ranges.
- `TypeArena` uses reserved primitive IDs and canonical structural, nominal,
  type-parameter, and instantiated keys with checkpoint/rollback.
- `SemanticState` stores explicit scope, declaration, node-type, call-target,
  storage, signature, and mutability associations.
- `DiagnosticArena` stores bounded structured diagnostics in deterministic
  insertion order and preserves fatal verifier context.
- `PhaseOrchestrator` enforces phase order and transactional commit/rollback;
  dependent phases are suppressed after failure.
- `WholeProgramContext.compose` consumes explicitly prepared artifacts,
  validates the existing IR verifier, and reports `TEST_ARTIFACT_INPUT=true`.
- `compile_program` fails closed without prepared artifacts; it is not a real
  source-to-output compiler.
- S3 projections use flat/parallel data and direct IDs. `vector<Composite>`
  remains outside the current representability boundary.

## Evidence

```text
PROGRAM_REGISTRY_DIFFERENTIAL=PASS
TYPE_ARENA_DIFFERENTIAL=PASS
DIAGNOSTIC_DIFFERENTIAL=PASS
ANTI_SPECIALIZATION=PASS (256 composition cases)
SCALING_PROGRAM_REGISTRY=PASS_BOUNDED
SCALING_TYPE_ARENA=PASS_BOUNDED
SCALING_PHASE_ROLLBACK=PASS_BOUNDED
SCALING_DIAGNOSTICS=PASS_BOUNDED

NATIVE_CONTROL_PLANE_CASES=64
NATIVE_CONTROL_PLANE_PASS=64
NATIVE_CONTROL_PLANE_FAIL=0
HOSTED_NATIVE_DIFFERENTIAL_CASES=64
HOSTED_NATIVE_DIFFERENTIAL_PASS=64
HOSTED_NATIVE_DIFFERENTIAL_FAIL=0
COMPOSITION_CORPUS_CASES=256
COMPOSITION_CORPUS_PASS=256
COMPOSITION_CORPUS_FAIL=0
SOAK_PASSES=3
SOAK_NONDETERMINISM=0

WINDOWS_FULL_TESTED_HEAD=e4d7aa5492e597da8f730671727f8bd5c66180d2
WINDOWS_FULL_SELECTED=4178
WINDOWS_FULL_PASSED=3870
WINDOWS_FULL_SKIPPED=308
WINDOWS_FULL_FAILED=0
WINDOWS_FULL_ERRORS=0
WINDOWS_FULL_EXIT=0

LINUX_FULL_TESTED_HEAD=3e2db7a8dc1bd6d97b4fbff6026c9692a047b5
LINUX_FULL_SELECTED=4178
LINUX_FULL_PASSED=4176
LINUX_FULL_SKIPPED=1
LINUX_FULL_FAILED=1
LINUX_FULL_ERRORS=0
LINUX_FULL_EXIT=1
LINUX_FULL_FAILURE=test_public_package_exports_remain_small
LINUX_FULL_FAILURE_CLASS=SOURCE_REGRESSION_IN_PREVIOUS_CANDIDATE
LINUX_FULL_FAILURE_FIX=The whole-program symbols were removed from __all__ while compile_program remained directly importable; focused post-fix proof passed on e4d7aa5.

LINUX_POST_FIX_FOCUSED=PASS
LINUX_POST_FIX_NATIVE=PASS
LINUX_POST_FIX_COMPILEALL=PASS
LINUX_POST_FIX_DIFF_CHECK=PASS
WINDOWS_POST_FIX_FOCUSED=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
```

The Linux full transcript is preserved in `evidence/linux-full-suite.txt`.
It ran before the narrow export-surface repair, so it is not silently reported
as evidence for the later source HEAD. The focused post-fix evidence is in
`evidence/linux-focused-post-fix.txt`; no second Linux full suite was started.
The Windows full transcript is in `evidence/windows-full-suite.txt`.

## Gate assessment

```text
SELFHOST_GATE_2=SUBSTANTIALLY_IMPROVED
SELFHOST_GATE_3=DESIGNED_NOT_IMPLEMENTED
SELFHOST_GATE_4=CONTROL_PLANE_SUPPORTED_PREPARED_ARTIFACTS_ONLY
SELFHOST_GATE_6=SUBSTANTIALLY_IMPROVED
SELFHOST_GATE_9=PARTIAL_OUTPUT_SINK_WITHOUT_EMITTER
SELFHOST_GATE_10=PASS_TRANSACTIONAL_PHASE_STATE
SELFHOST_GATE_11=PASS_NO_ID_RECOUNT

WHOLE_PROGRAM_COMPILER_CONTROL_PLANE=SUPPORTED
TRUE_COMPILE_PROGRAM_IMPLEMENTED=NO
LEXER_EXECUTED=NO
PARSER_EXECUTED=NO
SEMANTIC_EXPRESSION_ANALYZER_EXECUTED=NO
GENERIC_LOWERING_EXECUTED=NO
EMITTER_EXECUTED=NO
```

`READY_FOR_MAIN_MERGE=NO` because the only Linux full run captured a real,
source-level export regression in the predecessor candidate. The regression
was repaired and directly re-proven by focused Linux/Windows tests, native
tests, `compileall`, and `diff --check`, but the policy explicitly avoids
looping full suites. A fresh full-Linux certification for `e4d7aa5` remains the
next evidence gate before merge readiness can be claimed.

The largest remaining representability blocker is:

```text
NEXT_SELFHOST_REPRESENTABILITY_BLOCKER=PARSER_FRONTEND
```

The control plane is now explicit, but no S3 parser or source-to-output path
exists yet. This does not authorize self-host re-entry or Stage1 V4.

## Publication state

One Draft PR is permitted for review. It must remain unmerged and must state
the stale Linux full-gate evidence and the focused post-fix classification
explicitly. No release, tag, PyPI publication, merge, or machine shutdown is
authorized by this increment.

```text
CI_STATE=TO_BE_RECORDED_AFTER_DRAFT_PR
PR_MERGED=NO
READY_FOR_MAIN_MERGE=NO
NEXT_HARD_GATE=FRESH_LINUX_FULL_CERTIFICATION_ON_e4d7aa5492e597da8f730671727f8bd5c66180d2
```
