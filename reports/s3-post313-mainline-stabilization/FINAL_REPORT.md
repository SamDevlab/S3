# Post-#313 Mainline Stabilization

Date: 2026-09-24
Base: `c62496b6dc5252e2cfe0a8b54fe7c7ea4ea68034`
Branch: `chore/s3-post313-mainline-stabilization`

## Canonical project state

```text
MAIN_POST_313_INTEGRATION=YES
PR301_309_CAPABILITIES_IN_MAIN=YES
INTEGRATION_PATH=PR313
PR301_309_STACKED_INTEGRATION_BLOCKER=NO
PUBLIC_STABLE=v1.0.0
REFERENCE_COMPILER=PYTHON
FULL_SELFHOST=DEFERRED_RESEARCH
FULL_SELFHOST_CLAIMED=NO
S3_1_1_TECHNICAL_CLOSURE=PASS_PR294_MERGED
S3_1_1_RELEASE_PREP=PR295_OPEN_DRAFT_CONFLICTING
S3_1_2_STATE=ACTIVE_NATIVE_BACKEND_PRODUCTIONIZATION
```

PR #313 is merged into `main` at the base above. PR #301 is also merged
individually; PRs #302–#309 remain open Draft artifacts, but their cumulative
capabilities are on `main` through #313. Their open review state is historical
stack residue, not a missing integration dependency. PRs #310–#312 remain
separate open Draft exact-segment budget research/review work and were not
changed.

The 1.1 reliability implementation R0–R5 is technically closed in `main` via
PR #294. Its separate 1.1.0 release-preparation PR #295 remains open Draft and
is currently conflicting with `main`; no release decision is implied here.

## Compiler architecture audit

| Classification | Components and current boundary |
| --- | --- |
| `REFERENCE` | `bootstrap/s3/` is the complete Python reference compiler and default production compilation path. |
| `HOSTED_GENERIC` | `generic_lexer`, `generic_parser`, `generic_syntax`, `generic_ir`, `generic_verifier`, `frontend_registration`, type bridges, and `whole_program` provide generic hosted contracts/control-plane foundations. The generic real-source path is staged and does not replace the production reference pipeline. |
| `S3_NATIVE_EXPERIMENTAL` | S3-written substrate modules provide bounded source-derived lexer/parser/program and semantic execution slices, with typed-value and indexed-data protocols. These execute as S3 programs through the existing compiler/backend; they are not a compiler that compiles itself. |

Integrated capability boundaries:

- Native source frontend/program structure: bounded, source-derived lexer and
  parser/program slices in `selfhost/substrate/generic_lexer_state.s3`.
- Native semantic execution: bounded i64 subset in
  `selfhost/substrate/native_semantic_execution.s3`.
- Typed values and indexed data: bounded i64/f64 value/data contracts in
  `native_typed_value_protocol.s3` and `native_indexed_value_protocol.s3`;
  this is not full general-purpose S3-native semantic analysis.
- Aggregate references: immutable, call-bounded references to known records
  are supported in the compiler IR/runtime/native lowering path. This is not
  evidence of a complete S3-written aggregate compiler.
- Scientific RMSD: the narrow S3 source workload composes indexed f64 vector
  reads, arithmetic, division, and `sqrt`; the Linux x86-64 executable was
  compiled by the Python reference compiler. This is a native workload result,
  not self-hosted compilation.

There is intentional contract overlap between the hosted generic frontend and
the S3-written bounded slices for differential comparison. No duplicate
production compiler path was found. Historical reports remain unchanged where
their narrower statements were accurate at the time they were written; the
current state is clarified in `docs/selfhost/STATUS.md` and this report.

### `generic_lexer_state.s3` size and cohesion

The file is 4,066 lines. Its responsibilities are:

1. Lines 1–491: lexer state, character/token classification, and token scan.
2. Lines 492–2,066: expression and bounded program-parser logic.
3. Lines 2,067–2,955: S3 source byte/word construction and versioned program
   fixture builders.
4. Lines 2,956–3,196: statement parsing and program digest handling.
5. Lines 3,197–4,066: sequence/identifier fixture construction and parser
   probes.

The lexer/parser pipeline is conceptually related, but the module also owns
substantial test-program construction and probe logic. Other substrate modules
reuse its source-builder helpers, so extraction would require an explicit
module/interface boundary rather than a mechanical file split. This is a real
maintenance concentration, but no correctness defect was established and a
behavior-preserving refactor is outside this stabilization scope:

```text
MONOLITH_COHESION=PARTIAL
FUTURE_DECOMPOSITION_ADVISABLE=YES
MONOLITH_REFACTOR=DEFERRED
```

## P2 reconciliation

```text
P2_IN_MAIN=NO
P2_DEFAULT=NO
PER_INSTRUCTION_DEFAULT=YES
P2_SELECTED_CANDIDATE=1a76e341098b54a639fec22eecea362cc243c46f
P2H_STATUS=REJECTED_AS_STRUCTURALLY_IMMATERIAL_REPLACEMENT
P2_PARENT_STACK_BLOCKER=RESOLVED_BY_PR313
P2_CODE_SIZE_POLICY=OPEN
P2_MAINLINE_PORT_OR_REBASE=REQUIRED
P2_FRESH_VALIDATION=REQUIRED
P2_FRESH_BENCHMARK_COMPARISON=REQUIRED
P2_PROMOTION_AUTHORIZED=NO
```

The current #310–#312 branches are based on the pre-integration scientific
kernel branch, not current `main`. The former parent-stack blocker is resolved
by #313, but that does not satisfy code-size policy, a clean port/rebase,
fresh correctness and performance comparisons, CI/infrastructure, or product
promotion decisions. Compact EA's existing opt-in policy is distinct from this
exact-segment P2 and does not make P2 part of `main`.

## Infrastructure and branch policy

```text
GITHUB_ACTIONS_STATUS=BLOCKED_BY_BILLING_OR_QUOTA
GITHUB_ACTIONS_USED=NO
CI_RERUN_ATTEMPTED=NO
WORKFLOW_CHANGED=NO
INFRA_284=OPEN_BLOCKER
MAIN_PROTECTED=NO
REQUIRED_STATUS_CHECKS=NONE
MAIN_PROTECTION_DEBT=OPEN
```

Issue #284 remains open. The GitHub branch-protection endpoint reports that
`main` is not protected, and the repository rulesets endpoint returned an
empty list. Consequently no required checks, force-push restriction, or branch
deletion restriction is enforced by a discovered branch-protection/ruleset
policy. No protection settings were changed because Actions cannot currently
execute its checks. No CI pass is claimed.

## Local validation

Documentation-only stabilization; no Python, S3, test, compiler, runtime,
backend, or workflow files were changed.

Focused command executed on Windows:

```powershell
python -m pytest -q tests/test_source_frontend.py tests/test_frontend_registration.py tests/test_frontend_types.py tests/test_whole_program_composition.py tests/test_native_frontend_slice.py tests/test_native_semantic_execution.py tests/test_native_indexed_data.py tests/test_aggregate_function_results.py tests/test_scientific_kernel.py tests/test_native_x86_64_integration.py tests/test_native_x86_64.py
```

Result: exit 0. Pytest's quiet configuration emitted progress markers but no
aggregate count; platform-gated native cases displayed skips on Windows. The
previous full Linux suite remains separate source-freeze evidence from PR #313:
4,350 passed, 1 skipped, 0 failed, exit 0, on
`d064c17ea811ab926df515cb90884e8c6efffb3d`; transcript SHA-256 is
`74e98bd885edb120d383ae049a404973e92fc341bd0c152a3164502e8aa7f922`. It was
not rerun because this campaign changed documentation only.

```text
VALIDATION_MODE=LOCAL
LOCAL_VALIDATION=PASS
LOCAL_LINUX_GATE=PASS_INHERITED_FROM_PR313_SOURCE_FREEZE
GITHUB_ACTIONS_USED=NO
GITHUB_ACTIONS_STATUS=BLOCKED_BY_BILLING_OR_QUOTA
CI_RERUN_ATTEMPTED=NO
WORKFLOW_CHANGED=NO
COMPILEALL=NOT_RUN_DOCUMENTATION_ONLY
FULL_SUITE_RUN_THIS_CAMPAIGN=NO
DIFF_CHECK=PASS
```

## Changes and disposition

Canonical current-state updates were limited to `docs/roadmap/ACTIVE_TRACK.md`,
`docs/selfhost/STATUS.md`, `selfhost/README.md`, `README.md`, and a dated
post-merge reconciliation appended to the integration report. `CAMPAIGN_STATE_RESUME.json`
was inspected and left unchanged because it is a deprecated redirect to the
active track and its stable/reference/self-host values remain correct.

```text
POST313_BASELINE_CANONICALIZED=YES
MAIN_CAPABILITY_STATE_DOCUMENTED=YES
SELFHOST_STATUS_RECONCILED=YES
ACTIVE_TRACK_RECONCILED=YES
P2_PARENT_STACK_BLOCKER=RESOLVED
P2_PROMOTION_AUTHORIZED=NO
FULL_SELFHOST_CLAIMED=NO
EXECUTABLE_SOURCE_CHANGED=NO
TEST_SOURCE_CHANGED=NO
MAIN_MERGED=NO
NEW_RELEASE=NO
NEW_TAG=NO
PYPI_PUBLISHED=NO
FOLLOW_UP_RECOMMENDATION=PORT_AND_REASSESS_SELECTED_P2_ON_CURRENT_MAIN_WITH_CODE_SIZE_AND_FRESH_BENCHMARK_GATES
READY_FOR_P2_MAINLINE_CAMPAIGN=YES
```

This baseline is sufficiently documented and locally checked for a separate
P2 mainline-port campaign. That is only readiness to begin that work; it is not
P2 promotion authorization, and no P2 work is started here.
