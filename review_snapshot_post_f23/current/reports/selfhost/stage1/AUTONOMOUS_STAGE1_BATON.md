# S3 Rev39 Autonomous Stage1 Baton

This baton is append-only in substance. The earlier Rev39 history is preserved
in `AUTONOMOUS_BATON_REV39.md`; this file records the continuation checkpoint
used by the autonomous runner.

```text
CONTROL_REVISION=39
BRANCH=recovery/pr268-stage1-streaming-values-20260828
REPOSITORY_HEAD=1ec76af89992f119865a370488593ad5c85c4c49
COMPILER_CANDIDATE_SOURCE_PATH=selfhost/compiler/stage1_semantic_event_spine.s3
COMPILER_CANDIDATE_SOURCE_SHA=f334c76fcaa05c180d81933863d4d419eef07f221f92d170d3cf6ac8900245c3
CANONICAL_INPUT_SOURCE_PATH=selfhost/compiler/s3c_stage1.s3
CANONICAL_INPUT_SOURCE_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
CANONICAL_INPUT_BYTES=225699
CANONICAL_MUTATED=NO_OBSERVED; PREEXISTING_WORKTREE_CHANGE_PRESERVED
WORKTREE_STATUS=INTENDED_DIRTY_CHANGES_AND_UNTRACKED_CANDIDATE_PRESERVED
COMMIT=NO
PUSH=NO

CURRENT_PHASE=A_CONTROL_FLOW_V3
CURRENT_GATE=S1.2_FOCUSED_V3_MATRIX
CURRENT_FIRST_LOSS=CONTROL_FLOW_V3_COMPARE_BRANCH3_WHILE_NOT_IMPLEMENTED_IN_CANDIDATE_STREAM
LAST_COMPLETED_ACTION=MUTABLE_STORAGE_V3_FOUNDATION; D_TO_M_STORE_LOAD_STORAGE_PROVENANCE_MUTABLE_LITERAL_READ_ASSIGNMENT_ARITHMETIC_INITIALIZER_PASS
LAST_FOCUSED_RESULT=HOSTED_TEST_STAGE1_SEMANTIC_EVENT_SPINE_13_PASSED_21_SKIPPED_ON_WINDOWS
ORACLE_V3=LOCALLY_QUALIFIED_BY_PRESERVED_PROJECT_EVIDENCE; HOSTED_REFERENCE_MODEL_PRESENT
HOSTED_PARSE=PASS_FOR_CANDIDATE_SOURCE
HOSTED_SEMANTIC=PASS_FOR_CANDIDATE_SOURCE
HOSTED_LOWERING=PASS_FOR_CANDIDATE_SOURCE
NATIVE_BUILD=SKIPPED_ON_WINDOWS_PLATFORM; PRIOR_NATIVE_CANDIDATE_EVIDENCE_PRESERVED
FRAME_TRITS=217_HISTORICAL_CANDIDATE_CHECKPOINT
FRAME_LIMIT=131072
MIXED_PROVENANCE=NO_CURRENT_EVIDENCE; PRIOR_FREEZE_RISK_RECONCILED_BY_USER_AUTHORITATIVE_STATE
S1_2=OPEN_BLOCKED
S1_6=DEFERRED

EXPECTED=hosted_v3_COMPARE_real_V_then_BRANCH3_condition_edge_complete_T_and_while_JUMP_semantics
CANDIDATE=event_spine_has_parser_helpers_for_comparison_and_while_but_no_v3_COMPARE_BR3_T_or_loop-emission_lane
ROOT_CAUSE_HYPOTHESIS=bounded_candidate_lowering_stops_at_scalar_storage_and_return; control-flow records are not yet emitted
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED_THIS_CHECKPOINT=reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
NEXT_SAFE_ACTION=derive hosted-v3 records for the smallest noncanonical comparison and while fixtures; add one focused canary before patching candidate
```

## Checkpoint 2026-09-03 - SHARED CALL-ARGUMENT TYPE RESOLUTION

```text
ANALYSIS_INPUT=bounded generic additive call-relation canary plus focused call regression; canonical reprobe not repeated
CURRENT_CANDIDATE_SHA256=94001e8b9b068a72757732fd89d2f25593ff84e57ffdc691ba68c9afb8fb3a54
CURRENT_CANDIDATE_BYTES=1360702
CANONICAL_SHA256=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
CANONICAL_BYTES=225699
CANONICAL_PROBE_THIS_TURN=NO

SHARED_CONDITION_GENERALIZATION=PASS
GENERIC_CALL_RELATION_CANARY=PASS
ARG0_EXPRESSION_KIND=ADDITIVE
ARG0_TYPE_BEFORE=0
ARG0_TYPE_AFTER=3
PARAM0_TYPE=3
CALL_RETURN_TYPE_BEFORE=0
CALL_RETURN_TYPE_AFTER=2
CALLEE_FOUND=YES
CALL_SIGNATURE_FOUND=YES
RIGHT_LITERAL_VALUE=61
RIGHT_LITERAL_TYPE=3
EXPECTED_MATCH_RESULT_KIND=3
OBSERVED_MATCH_RESULT_KIND=3 in the generic canary
FIRST_DIVERGENT_SUBFIELD=ARG0_TYPE
NEW_SPECIALIZED_MATCH_HELPERS_ADDED=0

FOCUSED_CALL_REGRESSION=PASS; simple one-argument call edges and additive call-relation canary
TIER0=PASS; 5 passed, 2 skipped
TIER1_CURRENT_CANDIDATE=PASS
TIER2_CONTINUATION_REGRESSION=PASS; 62 passed
COMPILEALL=PASS
DIFF_CHECK=PASS

S1_2=OPEN
COMMIT=NO
PUSH=NO
CANONICAL_MUTATION=NO
CANONICAL_REPROBE=NO
STAGE2=NOT_STARTED
NEXT_SAFE_ACTION=await an explicitly authorized single canonical qualification after the current local gates; do not use canonical as a debugger
```

## Checkpoint 2026-09-03 - CANONICAL QUALIFICATION AFTER SHARED CALL-ARGUMENT FIX

```text
TIMESTAMP=2026-09-03T14:06:56.0761501-03:00
PHASE=CANONICAL_QUALIFICATION_AFTER_FIND_CALL_ARGUMENT_TYPE_BOUNDARY_FIX
BRANCH=recovery/pr268-stage1-streaming-values-20260828
HEAD=1ec76af89992f119865a370488593ad5c85c4c49
CANDIDATE_SHA_BEFORE=94001e8b9b068a72757732fd89d2f25593ff84e57ffdc691ba68c9afb8fb3a54
CANDIDATE_SHA_AFTER=94001e8b9b068a72757732fd89d2f25593ff84e57ffdc691ba68c9afb8fb3a54
CANDIDATE_BYTES_BEFORE=1360702
CANDIDATE_BYTES_AFTER=1360702
CANONICAL_SHA_BEFORE=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
CANONICAL_SHA_AFTER=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
CANONICAL_BYTES_BEFORE=225699
CANONICAL_BYTES_AFTER=225699
CANONICAL_PROBE=COMPLETED_EXIT_0
CANONICAL_PROBE_TRANSCRIPT=scratch/canonical-summary-20260903-20260903-103630384.txt
CANONICAL_PROBE_EXECUTION_SECONDS=12558.744264400002

F=14
B=405
D=29
V=657
M=11
I=1083
O=726
R=634
C=50
A=97
T=410
Z=0
FIRST_LOSS=after_function decimal_digit; completion record Z was not emitted
DIAGNOSTIC_CODE=S3IR2_CANONICAL_STREAM_INCOMPLETE
RULE_ID=S3.CONTROL.MATCH_THREE_WAY
FUNCTION_BOUNDARY_CROSSED=YES; F advanced from 10 to 14
Z_INTERPRETATION=not a semantic EOF/function-completion diagnosis; canonical-summary invokes scan_program directly and bypasses main finalization
NEXT_LOCAL_ACTION=bounded generic diagnosis around decimal_digit/function-finalization transition; do not use Z as a debugger

FOCUSED_CANARY=PASS
TIER0=PASS; 5 passed, 2 skipped
TIER1=PASS
TIER2=PASS; 62 passed
COMPILEALL=PASS
DIFF_CHECK=PASS
S1_2=OPEN
STAGE2=NOT_STARTED
COMMIT=NO
PUSH=NO
CANONICAL_MUTATION=NO
MIXED_PROVENANCE=NO
```

## Prior Rev39 history pointer

The chronological semantic/storage checkpoints, prior candidate hashes, and
the preserved oracle/native evidence remain in
`reports/selfhost/stage1/AUTONOMOUS_BATON_REV39.md`. No prior evidence is
deleted or rewritten by this continuation baton.

## CHECKPOINT 2026-08-29T08:00:00-03:00 — RELATIONAL COMPARE AND BRANCH3

```text
CANDIDATE_START_SHA=f334c76fcaa05c180d81933863d4d419eef07f221f92d170d3cf6ac8900245c3
CANDIDATE_END_SHA=030f021f9dea99d64c81f1ff23443f3bf9eb7ebb73681487332e3f97b168ad82
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_A_CONTROL_FLOW_V3
FIRST_SEMANTIC_LOSS=Resolved the first comparison loss: the candidate previously emitted only legacy lexical V observations for relational constructs and had no v3 COMPARE producer or complete BRANCH3 T representation.
EXPECTED_VS_CANDIDATE=Hosted direct <=> returns a real trit V produced by COMPARE; hosted match consumes that raw -1/0/1 relation through BRANCH3 negative/zero/positive edges. Candidate now emits this for bounded mutable-identifier <=> integer fixtures; loop/backedge and other operand families remain open.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py: PASS; 14 non-skipped tests passed, native Linux-only cases skipped on Windows
ORACLE_TESTS=Hosted direct compare and match relation-lane canaries: PASS; hosted COMPARE/BRANCH3 opcode and -1/0/1 target order verified
HOSTED_PARSE=PASS; candidate source compiles through hosted parser/semantic/lowering; 155 functions and 17468 hosted registers in this checkpoint
HOSTED_SEMANTIC=PASS for the new noncanonical compare/match canaries; canonical semantic conformance not run
HOSTED_LOWERING=PASS for the new noncanonical compare/match canaries
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; build attempt is unavailable on this Windows host because Stage1 requires Linux x86-64 and cc/gcc/clang; historical native evidence for the prior storage checkpoint is preserved
FRAME_METRIC=217 trits at the last measured candidate checkpoint; new source requires a fresh native frame measurement before Stage1 evidence can close
CANONICAL_MUTATED=NO_OBSERVED; required canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
S1_2=OPEN_BLOCKED pending remaining Phase A control families and fresh candidate-native evidence; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Continue Phase A with hosted-equivalent target/loop semantics: qualify zero/one/multiple while behavior, loop storage identity, backedge JUMP/T, break preservation, and the mutable dependent initializer/use path. Keep C/A closed until that matrix is green.
```

## CHECKPOINT 2026-08-29T08:25:00-03:00 — CONSTANT AND TRUTHY WHILE CONTROL

```text
CANDIDATE_START_SHA=030f021f9dea99d64c81f1ff23443f3bf9eb7ebb73681487332e3f97b168ad82
CANDIDATE_END_SHA=aef98c11a22306b3aca66ad8868e84d3695d53b03d2dc1b86d477f1aee11c244
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_A_CONTROL_FLOW_V3
FIRST_SEMANTIC_LOSS=Resolved hosted constant-loop behavior and the first dynamic truthy-loop/break graph. Hosted while 0 and while 1 omit the loop body; dynamic truthy control has entry JUMP, condition BRANCH3, three target lanes, break JUMP to the shared exit, and one T per terminated block.
EXPECTED_VS_CANDIDATE=Hosted constant while bodies are absent from the v3 graph; hosted dynamic truthy while preserves raw -1/0/1 target ordering and break control flow. Candidate now emits these rules for bounded literal/mutable-trit truthy loops with break-only bodies and returns, using indentation-bounded body skipping; compare conditions, backedges, and general bodies remain open.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py: PASS; 18 non-skipped tests passed, native Linux-only cases skipped on Windows
ORACLE_TESTS=Hosted constant while and truthy while canaries: PASS; block order, opcode families, target order, and break exit target verified
HOSTED_PARSE=PASS; candidate source compiles through hosted parser/semantic/lowering; 160 functions and 18611 hosted registers in this checkpoint
HOSTED_SEMANTIC=PASS for new noncanonical while canaries; canonical semantic conformance not run
HOSTED_LOWERING=PASS for new noncanonical while canaries
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; Stage1 build requires Linux x86-64 with cc/gcc/clang and this host is Windows; historical native evidence preserved
FRAME_METRIC=217 trits at last measured pre-control checkpoint; fresh native frame measurement remains required
CANONICAL_MUTATED=NO_OBSERVED; required canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
S1_2=OPEN_BLOCKED pending comparison while/backedge, zero/one/multiple dynamic iteration coverage, general break preservation, and fresh candidate-native evidence; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Implement the first hosted dynamic comparison while graph for a mutable dependent initializer, including COMPARE result, BRANCH3 condition edge, loop body storage identity, backedge JUMP/T with no V, and the final exit return. Preserve constant/truthy/break canaries.
```

## CHECKPOINT 2026-08-29T09:00:00-03:00 — DYNAMIC COMPARE WHILE WITH STORAGE BACKEDGE

```text
CANDIDATE_START_SHA=aef98c11a22306b3aca66ad8868e84d3695d53b03d2dc1b86d477f1aee11c244
CANDIDATE_END_SHA=d84dd09608b12d080cb9596ed6b0baad57f6da34b0149d9777b7ad990af65c1c
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_A_CONTROL_FLOW_V3
FIRST_SEMANTIC_LOSS=Resolved the first dynamic comparison-loop loss for a bounded mutable identifier <=> integer condition with one mutable additive body assignment and a final mutable return.
EXPECTED_VS_CANDIDATE=Hosted lowering has entry JUMP, condition index/LOAD/CONST/COMPARE/BRANCH3, body index/LOAD/CONST/ADD/index/STORE/backedge JUMP, zero/positive exits, and a final storage LOAD/RETURN. Candidate now emits the same six-block control graph, preserves M storage 0 through condition/body/final loads, and emits no V for either backedge JUMP.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py: PASS; 20 non-skipped tests passed and Linux-only native cases skipped on Windows
ORACLE_TESTS=Hosted dynamic compare-loop canary: PASS; six blocks, raw COMPARE result, BRANCH3 target order, storage identity, additive body, and JUMP backedge verified
HOSTED_PARSE=PASS; candidate source compiles through hosted parser; 161 functions and 19853 hosted registers at this checkpoint
HOSTED_SEMANTIC=PASS for candidate source and new noncanonical loop canary; canonical semantic conformance not run
HOSTED_LOWERING=PASS for candidate source and new noncanonical loop canary
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; Stage1 native build requires Linux x86-64 with cc/gcc/clang and this host is Windows; historical native evidence preserved
FRAME_METRIC=217 trits at last measured pre-control checkpoint; fresh native frame measurement remains required
CANONICAL_MUTATED=NO_OBSERVED; required canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
S1_2=OPEN_BLOCKED pending dynamic zero/one/multiple iteration matrix, general body/break coverage, mutable dependent initializer/use path, and fresh candidate-native evidence; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Continue Phase A with dynamic loop iteration canaries and mutable dependent initializer position + 1, then qualify the noncanonical position + 1 -> mutable end -> LOAD -> COMPARE -> BRANCH3 path. Keep C/A closed until the full control-flow matrix is green.
```

## CHECKPOINT 2026-08-29T09:35:00-03:00 — MUTABLE DEPENDENT INITIALIZER AND TWO-STORAGE COMPARE

```text
CANDIDATE_START_SHA=d84dd09608b12d080cb9596ed6b0baad57f6da34b0149d9777b7ad990af65c1c
CANDIDATE_END_SHA=c4c5f5ca4040940eb08ad7603d4358335fafe4aa864cc0337683d0ad29b896ae
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_A_CONTROL_FLOW_V3
FIRST_SEMANTIC_LOSS=Resolved the dependent mutable-initializer and mutable-right-operand loss: position + 1 now materializes end through a real load/add/store sequence, and position <=> end loads both M storages before COMPARE.
EXPECTED_VS_CANDIDATE=Hosted entry has six instructions for mut end = position + 1; the dynamic condition has left index/load, right index/load, COMPARE, BRANCH3; the body updates only position; the loop backedge and exits are JUMP/T with no V. Candidate adds that rule, updates instruction counting, and emits the two-storage six-block graph with the correct V/I/O/R/T relationships.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py: PASS; 23 non-skipped tests passed and Linux-only native cases skipped on Windows
ORACLE_TESTS=Hosted iteration matrix and dependent-initializer canaries: PASS; zero/one/multiple iteration edge shapes, two mutable storage loads, COMPARE operands, BRANCH3 targets, and backedge verified
HOSTED_PARSE=PASS; candidate source compiles through hosted parser/semantic/lowering; 163 functions and 21445 hosted registers at this checkpoint
HOSTED_SEMANTIC=PASS for candidate source and new noncanonical dependent-loop canaries; canonical semantic conformance not run
HOSTED_LOWERING=PASS for candidate source and new noncanonical dependent-loop canaries
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; Stage1 native build requires Linux x86-64 with cc/gcc/clang and this host is Windows; historical native evidence preserved
FRAME_METRIC=217 trits at last measured pre-control checkpoint; fresh native frame measurement remains required
CANONICAL_MUTATED=NO_OBSERVED; required canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
S1_2=OPEN_BLOCKED pending relational true/false lowering families, general loop body/break coverage, full focused matrix, canonical probe, and fresh candidate-native evidence; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Qualify relational operators whose hosted result is a raw COMPARE followed by BRANCH3 and trit-valued lane stores; preserve the existing <=> path and keep C/A closed until Phase A is complete.
```

## CHECKPOINT 2026-08-29T12:39:05-03:00 — RELATIONAL WHILE WITH MUTABLE RIGHT OPERAND

```text
CANDIDATE_START_SHA=c4c5f5ca4040940eb08ad7603d4358335fafe4aa864cc0337683d0ad29b896ae
CANDIDATE_END_SHA=c3aff98c8d761a298b10ee77a61592432d67b335d9922638debd029afc185133
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_A_CONTROL_FLOW_V3
FIRST_SEMANTIC_LOSS=Resolved the mutable-right relational loop shape exposed by the hosted position < end model.
EXPECTED_VS_CANDIDATE=Hosted lowering loads both mutable operands before raw COMPARE, routes the result through relation-specific -1/0 lanes in a temporary trit M, then BRANCH3s to loop body or exits. Candidate adds the same bounded 10-block graph for all six relational operators, preserves both M identities, body backedge JUMP/T, and one T per terminated block.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py: PASS; 41 non-skipped tests passed and Linux-only native cases skipped on Windows
ORACLE_TESTS=Hosted mutable-right relational while canaries for <, <=, >, >=, ==, !=: PASS; 3 memory objects, 27 registers, dual condition LOADs, relation lanes, continuation BRANCH3, and backedge verified
HOSTED_PARSE=PASS; candidate source compiles through hosted parser/semantic/lowering; 168 functions and 25983 hosted registers at this checkpoint
HOSTED_SEMANTIC=PASS for candidate source and new mutable-right relational-loop canaries; canonical semantic conformance not run
HOSTED_LOWERING=PASS for candidate source and new mutable-right relational-loop canaries
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; Stage1 native build requires Linux x86-64 with cc/gcc/clang and this host is Windows; historical native evidence preserved
FRAME_METRIC=217 trits at last measured candidate checkpoint; fresh native frame measurement remains required
CANONICAL_MUTATED=NO_OBSERVED; required canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
S1_2=OPEN_BLOCKED pending broader Phase A control/generalization coverage, full focused matrix, canonical probe, and fresh candidate-native evidence; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Continue Phase A with broader loop-body and break generalization, then qualify the full focused V3 matrix before opening C/A. Preserve the new mutable-right relation canary and keep canonical input untouched.
```

## CHECKPOINT 2026-08-29T12:55:00-03:00 — PARAMETER V/D AND DIRECT COMPARE MATCH

```text
CANDIDATE_START_SHA=c3aff98c8d761a298b10ee77a61592432d67b335d9922638debd029afc185133
CANDIDATE_END_SHA=03ab5e7a87b3d991246c465d7001f408a480ffda5e899b29241ce08572a75ef9
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_A_CONTROL_FLOW_V3
FIRST_SEMANTIC_LOSS=Resolved parameter-backed compare/match lowering exposed by the canonical is_digit shape.
EXPECTED_VS_CANDIDATE=Hosted parameter match uses an existing parameter V directly, emits only CONST then COMPARE then BRANCH3 in the entry block, and returns one literal from each lane. Candidate now emits parameter-counted F, parameter V/D binding records, a direct parameter compare graph, and parameter return edges without a synthetic storage load.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py: PASS; 42 non-skipped tests passed and Linux-only native cases skipped on Windows
ORACLE_TESTS=Hosted parameter-backed compare/match canary: PASS; parameter register operand, COMPARE producer, BRANCH3 lanes, and literal returns verified
HOSTED_PARSE=PASS; candidate source compiles through hosted parser/semantic/lowering; 172 functions and 27315 hosted registers at this checkpoint
HOSTED_SEMANTIC=PASS for candidate source and parameter compare/match canary; canonical semantic conformance not run
HOSTED_LOWERING=PASS for candidate source and parameter compare/match canary
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; Stage1 native build requires Linux x86-64 with cc/gcc/clang and this host is Windows; historical native evidence preserved
FRAME_METRIC=217 trits at last measured candidate checkpoint; fresh native frame measurement remains required
CANONICAL_MUTATED=NO_OBSERVED; required canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
S1_2=OPEN_BLOCKED pending parameter return/general control coverage, full focused matrix, canonical probe, and fresh candidate-native evidence; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Continue Phase A by qualifying match relation conversion for parameter-backed equality/ordering and generalized break/body control. Keep C/A closed until the control-flow matrix is complete.
```

## CHECKPOINT 2026-08-29T14:04:48-03:00 — PARAMETER-RIGHT RELATIONAL WHILE WITH INCREMENT

```text
CANDIDATE_START_SHA=03ab5e7a87b3d991246c465d7001f408a480ffda5e899b29241ce08572a75ef9
CANDIDATE_END_SHA=eb3dbf8922b4e19b08ba2be46363136e64a89fca
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_A_CONTROL_FLOW_V3
FIRST_SEMANTIC_LOSS=Resolved the parameter-right relational while loss exposed by the hosted loop fixture: a mutable left local can compare directly against a parameter and update with += literal.
EXPECTED_VS_CANDIDATE=Hosted lowering has a parameter V in register 0, left index/LOAD, raw COMPARE against that parameter, BRANCH3 relation lanes, body index/LOAD/CONST/ADD/index/STORE/backedge JUMP, two exit JUMPs, final LOAD/RETURN, and three relation-lane stores through a temporary trit M. Candidate now emits the same 10-block shape, with no V for the backedge and a complete terminating T.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py: PASS; all non-skipped tests passed and Linux-only native cases skipped on Windows
ORACLE_TESTS=Hosted parameter-right relational while canary: PASS; 10 blocks, 21 registers, 2 memory objects, parameter COMPARE operand, relation BRANCH3 targets, += body, and backedge verified
HOSTED_PARSE=PASS; candidate source compiles through hosted parser/semantic/lowering; 258 functions and 32738 hosted registers at this checkpoint
HOSTED_SEMANTIC=PASS for candidate source and new parameter-right noncanonical canary; canonical semantic conformance not run
HOSTED_LOWERING=PASS for candidate source and new parameter-right noncanonical canary
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; Stage1 native build requires Linux x86-64 with cc/gcc/clang and this host is Windows; historical native evidence preserved
FRAME_METRIC=217 trits at last measured candidate checkpoint; fresh native frame measurement remains required
CANONICAL_MUTATED=NO_OBSERVED; required canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
DIFF_CHECK=PASS; git diff --check emitted no whitespace errors
S1_2=OPEN_BLOCKED pending generalized loop-body/break coverage, full focused matrix, canonical probe, and fresh candidate-native evidence; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Run exactly one candidate hosted-v3 canonical probe and stop at its first semantic loss. If canonical advances, isolate the next smallest noncanonical construct before changing C/A.

## CHECKPOINT 2026-08-29T14:18:00-03:00 — PARAMETER-RIGHT NESTED COMPOUND LOOP

```text
CANDIDATE_START_SHA=eb3dbf8922b4e19b08ba2be46363136e64a89fca
CANDIDATE_END_SHA=54fa3e60470075c361663b0f8cd3c0803db35d88e36a0d589ce86483937a7c00
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_A_CONTROL_FLOW_V3
FIRST_SEMANTIC_LOSS=Resolved the nested compound-loop loss exposed by the hosted position + 1, result < end fixture.
EXPECTED_VS_CANDIDATE=Hosted lowering includes explicit relation-lane JUMPs for the outer and inner matches, complete T edges, and the mutable initializer instructions before the outer entry jump. Candidate now emits the same bounded 19-block/78-instruction structure while preserving mutable storage identity and no-V backedges.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py: PASS; all non-skipped tests passed and Linux-only native cases skipped on Windows
ORACLE_TESTS=Hosted nested compound-loop canary: PASS; 19 blocks, 78 instructions, nested relation lanes, complete T edges, mutable initializer/body storage, and backedge verified
HOSTED_PARSE=PASS; candidate source compiles through hosted parser/semantic/lowering
HOSTED_SEMANTIC=PASS for candidate source and nested compound-loop canary; canonical semantic conformance not run
HOSTED_LOWERING=PASS for candidate source and nested compound-loop canary
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; Stage1 native build requires Linux x86-64 with cc/gcc/clang and this host is Windows; historical native evidence preserved
FRAME_METRIC=217 trits at last measured candidate checkpoint; fresh native frame measurement remains required
CANONICAL_MUTATED=NO_OBSERVED; required canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
DIFF_CHECK=PASS; git diff --check emitted no whitespace errors
S1_2=OPEN_BLOCKED pending the next canonical control-flow loss, generalized loop-body coverage, full focused matrix, canonical conformance, and fresh candidate-native evidence; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Add a noncanonical canary for a relational while containing a three-way match, call-bound mutable local, and nested call-based match; implement one structural lowering rule, then rerun focused tests and the canonical first-loss probe.
```

## CHECKPOINT 2026-08-29T14:42:00-03:00 — NESTED MATCH-CALL WHILE CANARY

```text
CANDIDATE_START_SHA=54fa3e60470075c361663b0f8cd3c0803db35d88e36a0d589ce86483937a7c00
CANDIDATE_END_SHA=5eb4c42465d5f34041e3f4077aa45d41f5c1d1ffc376e40166cc4b0c67225c17
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_A_CONTROL_FLOW_V3
FIRST_SEMANTIC_LOSS=Resolved the generic relational-while body loss for a three-way match with a call-bound mutable local and a nested call-based match.
EXPECTED_VS_CANDIDATE=Hosted lowering has 22 blocks, 84 instructions, 50 values, five memory objects, relation-lane JUMPs, a real M/D binding for unit, read_unit/is_blank CALL instructions, inner and outer BRANCH3 edges, and one T per block. Candidate now emits the same bounded CFG shape with referentially valid O/R edges and no V-producing backedge.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py: PASS; all non-skipped tests passed and Linux-only native cases skipped on Windows
ORACLE_TESTS=Hosted nested-match/call/while canary: PASS; 22 blocks, 84 instructions, 50 values, five memory objects, CALL/BRANCH3 shape, storage binding, complete T coverage, and O/R reference validity verified
HOSTED_PARSE=PASS; candidate source compiles through hosted parser/semantic/lowering
HOSTED_SEMANTIC=PASS for candidate source and nested-match/call/while canary; canonical semantic conformance not run
HOSTED_LOWERING=PASS for candidate source and nested-match/call/while canary
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; Stage1 native build requires Linux x86-64 with cc/gcc/clang and this host is Windows; historical native evidence preserved
FRAME_METRIC=217 trits at last measured candidate checkpoint; fresh native frame measurement remains required
CANONICAL_MUTATED=NO_OBSERVED; required canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
DIFF_CHECK=PASS; git diff --check emitted no whitespace errors
S1_2=OPEN_BLOCKED pending complete Phase A matrix review, canonical conformance, Phase B CALL C/A semantics, and fresh candidate-native evidence; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Re-run the full focused Phase A matrix is already green; now perform the next single canonical hosted-v3 probe and inspect only its first loss. If it reaches CALL metadata, close Phase A evidence and begin Phase B C/A.
```

## CHECKPOINT 2026-08-29T18:44:38-03:00 — ONE-ARGUMENT CALL C/A

```text
CANDIDATE_START_SHA=5eb4c42465d5f34041e3f4077aa45d41f5c1d1ffc376e40166cc4b0c67225c17
CANDIDATE_END_SHA=901b325399fe821773c0087567777b9f4fe60697395750df6131af6743890bd2
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_B_CALL_C_A_V3
FIRST_SEMANTIC_LOSS=Resolved the first one-argument call metadata loss: a result-producing direct call previously stopped after legacy V acceptance and emitted no call instruction graph.
EXPECTED_VS_CANDIDATE=Hosted read(x) -> host(x) has parameter V0, CALL result V1, I0 opcode CALL with O/R edges, C0 identifying foreign callee function 2 and name span 70:4, A0 ordered to V0, return I1/T1. Candidate now emits the same bounded graph.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py -k one_argument_call: PASS; 2 passed, Windows native cases not selected
ORACLE_TESTS=Hosted one-argument call canary: PASS; call result, foreign callee identity/kind/name span, ordered argument edge, and return terminator verified
HOSTED_PARSE=PASS; candidate source compiles through hosted parser/semantic/lowering; 201 functions and 43894 hosted registers
HOSTED_SEMANTIC=PASS for candidate source and one-argument call canary
HOSTED_LOWERING=PASS for candidate source and one-argument call canary
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; Stage1 native build requires Linux x86-64 and this host is Windows; prior native evidence preserved
FRAME_METRIC=217 historical candidate checkpoint; fresh native frame measurement remains required
CANONICAL_MUTATED=NO_OBSERVED; canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
DIFF_CHECK=PASS; git diff --check emitted no whitespace errors
S1_2=OPEN_BLOCKED; Phase B C/A migration is in progress; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Inspect hosted and candidate output for the existing three-argument call fixture; add the smallest general ordered-argument C/A canary before patching.
```

## CHECKPOINT 2026-08-29T19:01:07-03:00 — THREE-ARGUMENT CALL C/A

```text
CANDIDATE_START_SHA=901b325399fe821773c0087567777b9f4fe60697395750df6131af6743890bd2
CANDIDATE_END_SHA=cc1a5d44d813c5d8f938957fcad458a75c549c1e4d24a8335ff339f4912694d3
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_B_CALL_C_A_V3
FIRST_SEMANTIC_LOSS=Resolved the three-argument call metadata loss: the legacy pack-token recognizer accepted only its old shape and emitted no v3 call graph for a general three-argument result call.
EXPECTED_VS_CANDIDATE=Hosted probe(position) -> pack_token(position, 0, 0) has parameter V3, literal CONST V4/V5, CALL result V6, call I1000002 with three O edges, C identifying internal callee function 0 and name span, A ordinals 0/1/2 to V3/V4/V5, return I1000003/T. Candidate now emits the same bounded ordered graph and preserves the legacy pack-token acceptance matrix.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py -k "three_argument_call or one_argument_call": PASS; focused call canaries passed; full semantic-event-spine regression exited 0 with Windows-native cases skipped
ORACLE_TESTS=Hosted three-argument call canary: PASS; const ordering, internal callee identity/kind/name span, ordered A/O operands, result R, return T, and hosted call operands/results verified
HOSTED_PARSE=PASS; candidate source compiles through hosted parser/semantic/lowering; 209 functions and 45353 hosted registers
HOSTED_SEMANTIC=PASS for candidate source and one-/three-argument call canaries
HOSTED_LOWERING=PASS for candidate source and one-/three-argument call canaries
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; Stage1 native build requires Linux x86-64 and this host is Windows; historical native evidence preserved
FRAME_METRIC=217 historical candidate checkpoint; fresh native frame measurement remains required
CANONICAL_MUTATED=NO_OBSERVED; required canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
DIFF_CHECK=PASS; git diff --check emitted no whitespace errors
S1_2=OPEN_BLOCKED; Phase B C/A migration continues for remaining call families and full matrix; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Inspect the existing internal-call and discard/nested-call fixtures against hosted v3; add the smallest missing C/A canaries and preserve one- and three-argument regressions.
```

## CHECKPOINT 2026-08-29T19:42:00-03:00 — COMPLEX AND DISCARDED CALL C/A

```text
CANDIDATE_START_SHA=cc1a5d44d813c5d8f938957fcad458a75c549c1e4d24a8335ff339f4912694d3
CANDIDATE_END_SHA=442dee1b3def374e8645ad37c4569d422f055a04e4887f6caa2d11e3758d1fc3
CANONICAL_RAW_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
PHASE=PHASE_B_CALL_C_A_V3
FIRST_SEMANTIC_LOSS=Resolved the remaining focused C/A losses in nested foreign/internal call lowerings and supported discarded one-argument calls. Complex call instructions previously had O/R only; discarded calls omitted the result-producing call graph.
EXPECTED_VS_CANDIDATE=Hosted nested canaries expose read_unit(position), is_blank(unit), and sample(cursor) CALLs with one ordered operand and one result; hosted discard host(1) retains CONST/CALL/R with no terminator. Candidate now emits C/A for all explicit v3 call instructions, including foreign/internal identity and name spans, and emits a bounded discarded-call graph while preserving return T records.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED=selfhost/compiler/stage1_semantic_event_spine.s3; tests/test_stage1_semantic_event_spine.py; reports/selfhost/stage1/AUTONOMOUS_STAGE1_BATON.md
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py: PASS; full semantic-event-spine regression exited 0 with Windows-native cases skipped; one-/three-argument, nested, compound, and discard call canaries green
ORACLE_TESTS=Hosted call inventory and focused IR canaries: PASS; nested foreign/internal calls have one operand/result, three-argument order is preserved, and discarded call result producer is retained
HOSTED_PARSE=PASS; candidate source compiles through hosted parser/semantic/lowering; 214 functions and 45924 hosted registers
HOSTED_SEMANTIC=PASS for candidate source and all focused call/control-flow canaries
HOSTED_LOWERING=PASS for candidate source and all focused call/control-flow canaries
NATIVE_BUILD=NOT_RUN_AFTER_PATCH; Stage1 native build requires Linux x86-64 and this host is Windows; historical native evidence preserved
FRAME_METRIC=217 historical candidate checkpoint; fresh native frame measurement remains required
CANONICAL_MUTATED=NO_OBSERVED; required canonical raw SHA still matches; pre-existing canonical worktree modification preserved
MIXED_PROVENANCE=NO_OBSERVED
DIFF_CHECK=PASS; git diff --check emitted no whitespace errors
S1_2=OPEN_BLOCKED; Phase B focused C/A coverage is green; proceed to full focused v3 matrix and the next single canonical hosted-v3 probe; S1_6=DEFERRED; PACKED_1E12=DEFERRED
NEXT_SAFE_ACTION=Run the full focused semantic-event-spine matrix as the Phase C gate, then perform exactly one canonical hosted-v3 probe and inspect only its first semantic loss.

## Checkpoint 2026-08-29T20:04:01-03:00 — CANONICAL FIRST LOSS: LOOP CONTINUATION

TIMESTAMP=2026-08-29T20:04:01-03:00
CANDIDATE_START_SHA=925389350D02D2336FEB429F233292B19360E7FF540EBD7C742D47E0753498F3
CANDIDATE_END_SHA=925389350D02D2336FEB429F233292B19360E7FF540EBD7C742D47E0753498F3
COMPILER_CANDIDATE_SOURCE_SHA=925389350D02D2336FEB429F233292B19360E7FF540EBD7C742D47E0753498F3
CANONICAL_INPUT_SOURCE_SHA=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
PHASE=PHASE_E_CANONICAL_FIRST_LOSS_CONVERGENCE
FOCUSED_TESTS=FULL_SEMANTIC_EVENT_SPINE_SUITE_PASS; WINDOWS_NATIVE_SKIPS_EXPECTED
ORACLE_TESTS=FOCUSED_HOSTED_V3_CANARIES_PASS
HOSTED_PARSE_SEMANTIC_LOWERING=PASS_FOR_CANDIDATE_SOURCE; CANONICAL_HOSTED_REFERENCE_37_FUNCTIONS_3681_BLOCKS_58070_INSTRUCTIONS_862_CALLS
NATIVE_BUILD=NOT_RUN_ON_WINDOWS; PRESERVED_LINUX_NATIVE_EVIDENCE_PASS
FRAME_METRIC=217_TRITS_HISTORICAL_CANDIDATE_MEASUREMENT; LIMIT=131072
FIRST_SEMANTIC_LOSS=Canonical scan_token function, first general body after mut skipping: the outer while condition is skipping == -1 and its body is a three-way match with a call-bound mutable local and nested call match; the candidate emits the loop only for a direct-return tail and stops before the following match position >= length.
EXPECTED=Hosted v3 preserves the nested match-call loop CFG and continues its exits into the following match, with complete I/O/R/T edges.
CANDIDATE=Candidate v3 emits only the prefix through scan_token's initial storage declarations (F0-F9; 138 V, 213 I, 6 C, 6 A, 148 O, 124 R, 76 T, 74 B, 6 M) and fails closed before F10.
GENERALIZATION_CLASS=EXISTING_RULE_EXTENSION
FILES_CHANGED_THIS_CHECKPOINT=none_since_prior_candidate_checkpoint; diagnostic_only_canonical_probe
CANONICAL_PROBE=RAW_SHA_ASSERTED; SINGLE_COMPACT_DEFINITIVE_RESULT_RECOVERED; CANONICAL_MUTATED=NO; MIXED_PROVENANCE=NO
S1_2=OPEN_BLOCKED; S1_6=DEFERRED; PACKED_1E12=DEFERRED
DIFF_CHECK=PASS
NEXT_SAFE_ACTION=Add_a_noncanonical_nested_match_call_while_with_a_following_match_continuation_canary; extend_the_existing_structural_lowering_rule; rerun_focused_and_one_canonical_probe
```

## Checkpoint 2026-08-29T20:30:00-03:00 - CANONICAL LOOP-CONTINUATION REPROBE

```text
CANDIDATE_SOURCE_PATH=selfhost/compiler/stage1_semantic_event_spine.s3
CANDIDATE_SOURCE_SHA256=4875EB3B1B2068BC0990C4FE901E8B016DA984EA9D7265FB9E4454F05D06492F
CANDIDATE_SOURCE_BYTES=784498
CANONICAL_INPUT_SOURCE_PATH=selfhost/compiler/s3c_stage1.s3
CANONICAL_INPUT_SOURCE_SHA256=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_INPUT_SOURCE_BYTES=225699
PHASE=PHASE_E_CANONICAL_FIRST_LOSS_CONVERGENCE
FOCUSED_TESTS=FULL_SEMANTIC_EVENT_SPINE_SUITE_PASS; WINDOWS_NATIVE_SKIPS_EXPECTED
CONTINUATION_CANARY=HOSTED_CANDIDATE_NESTED_MATCH_CALL_WHILE_CONTINUATION_PASS; 29 BLOCKS; 107 INSTRUCTIONS; 29 TERMINATORS; 2 CALL C/A RECORDS
CANONICAL_PROBE=ONE_REPROBE_COMPLETE; F0-F9_EMITTED; F9_SCAN_TOKEN_PREFIX_ONLY; V=138; B=74; I=213; C=6; A=6; O=148; R=124; T=76
FIRST_SEMANTIC_LOSS=scan_token outer while skipping == -1 reaches the following match position >= length, whose negative and positive arms return pack_token(position, 0, 0) while the neutral arm discards 0 and continues into later function code.
ROOT_CAUSE=the existing nested-match loop lowering accepts a terminal all-return match or a direct-return tail, but has no joined continuation block/state for a mixed terminal/fallthrough match; scan_program consequently cannot place later statements in the correct successor block.
GENERALIZATION_CLASS=NEW_CONTROL_FLOW_JOIN_CONTEXT_REQUIRED; no canonical-specific offset or function-name rule is safe
EXPECTED_VS_CANDIDATE=Hosted IR has a three-way continuation match with two terminal CALL/RETURN arms and one fallthrough successor; candidate stops before that match and remains fail-closed rather than emitting an invalid target graph.
HOSTED_PARSE_SEMANTIC_LOWERING=PASS_FOR_CANDIDATE_SOURCE_AND_CONTINUATION_CANARY
NATIVE_BUILD=NOT_RUN_ON_WINDOWS; PRESERVED_LINUX_NATIVE_EVIDENCE_PASS
FRAME_METRIC=217_TRITS_HISTORICAL_CANDIDATE_MEASUREMENT; LIMIT=131072
CANONICAL_MUTATED=NO; MIXED_PROVENANCE=NO
S1_2=OPEN_BLOCKED; S1_6=DEFERRED; PACKED_1E12=DEFERRED
DIFF_CHECK=PASS_BEFORE_THIS_CHECKPOINT
NEXT_SAFE_ACTION=architect_and_implement_a_general_joined_control_flow_context_for_mixed_match_fallthrough_before_resuming_scan_token; do_not_simulate_the_missing_successor_or_claim_canonical_conformance
```
```

## Checkpoint 2026-08-29T21:43:46-03:00 - CONTINUATION CANARY GATE

```text
CANDIDATE_SOURCE_PATH=selfhost/compiler/stage1_semantic_event_spine.s3
CANDIDATE_SOURCE_SHA256=4875EB3B1B2068BC0990C4FE901E8B016DA984EA9D7265FB9E4454F05D06492F
CANDIDATE_SOURCE_BYTES=784498
CANONICAL_INPUT_SOURCE_PATH=selfhost/compiler/s3c_stage1.s3
CANONICAL_INPUT_SOURCE_SHA256=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_INPUT_SOURCE_BYTES=225699
PHASE=PHASE_E_CANONICAL_FIRST_LOSS_CONVERGENCE
FOCUSED_TESTS=python -m pytest -q tests/test_stage1_semantic_event_spine.py; PASS; EXIT=0
CONTINUATION_CANARY=PASS; NESTED_MATCH_CALL_WHILE_CONTINUATION; 29 BLOCKS; 107 INSTRUCTIONS; 29 TERMINATORS; 2 CALL C/A RECORDS
CANONICAL_PROBE=ONE_REPROBE_ALREADY_COMPLETE; NO_SECOND_REPROBE; CANDIDATE_SOURCE_UNCHANGED
FIRST_SEMANTIC_LOSS=scan_token outer while continuation reaches a mixed match position >= length; negative and positive arms return while the neutral arm falls through to later statements.
ROOT_CAUSE=the candidate has no general active successor-block context; scan_program can resume source scanning only with value-id state, while generic emitters still materialize later instructions in block 0. A partial fix would create invalid block ownership or target edges.
GENERALIZATION_CLASS=NEW_CONTROL_FLOW_JOIN_CONTEXT_REQUIRED
HOSTED_CANDIDATE_CONTINUATION=PASS; exact terminator target is 52 in the validated candidate stream
HOSTED_PARSE_SEMANTIC_LOWERING=PASS_FOR_CANDIDATE_SOURCE_AND_CANARY
NATIVE_BUILD=NOT_RUN_ON_WINDOWS; PRESERVED_LINUX_NATIVE_EVIDENCE_PASS
CANONICAL_MUTATED=NO; MIXED_PROVENANCE=NO
S1_2=OPEN_BLOCKED; safe implementation requires a general joined-CFG context before scan_token can be resumed; S1_6=DEFERRED; PACKED_1E12=DEFERRED
DIFF_CHECK=PASS
NEXT_SAFE_ACTION=design_and_implement_the_general_joined_control_flow_context; preserve_fail_closed_behavior_until_block_and_terminator_ownership_are_explicit
```

## Session Handoff 2026-08-29T22:58:55-03:00 - SUCCESSOR CONTEXT ADJACENT GATE BLOCKED

```text
CURRENT_CANDIDATE_SHA=1FC5ED99281938DF4FA4CC5D5513482BF7DCE986FFDFB7839883558C437BDED3
CURRENT_CANDIDATE_BYTES=811686
CURRENT_PHASE=PHASE_E_CANONICAL_FIRST_LOSS_CONVERGENCE
LAST_COMPLETED_GATE=MATCH_SUCCESSOR_CONTEXT_FOCUSED_PASS; NATIVE_V_REPLAY_PASS
FIRST_OPEN_GATE=ADJACENT_CALL_AND_PARAMETER_CONTRACT_RECONCILIATION
CURRENT_FIRST_LOSS_FUNCTION=scan_token
CURRENT_FIRST_LOSS_CONSTRUCT=LOOP_CONTINUATION / MATCH_FALLTHROUGH
FOCUSED_STATUS=BLOCKED_BY_PREEXISTING_CANONICAL_CONTRACT_MISMATCH
CALL_ARGUMENT_GATE=FAIL; historical closure pins source 20FDDBB.../166984 bytes/656 calls/736 arguments; current canonical is 44F02282.../225699 bytes and models 752 calls/831 arguments
PARAMETER_CAPACITY_GATE=FAIL; historical transformation anchors are absent from the current canonical shape
F3_F4_MIXED_NESTED_SUCCESSOR=NOT_PROVEN; current generic path remains fail-closed for exploratory nested mixed bodies
CANONICAL_SHA=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_MUTATED=NO_IN_THIS_RESUMPTION
CANONICAL_REPROBE=NOT_RUN; focused adjacent gates are not green
S1_2_STATUS=OPEN_BLOCKED
S1_6_STATUS=DEFERRED
SELF_EMIT=NOT_STARTED
STAGE1=NOT_STARTED
NEXT_SAFE_ACTION=Reconcile the historical CALL/C/A and parameter-capacity contracts against the preserved 44F02282... canonical source with fresh factual evidence; do not alter canonical or claim conformance
```

## Session Handoff 2026-08-29T23:32:00-03:00 - HISTORICAL CONTRACTS RECONCILED

```text
CURRENT_CANDIDATE_SHA=1FC5ED99281938DF4FA4CC5D5513482BF7DCE986FFDFB7839883558C437BDED3
CURRENT_CANDIDATE_BYTES=811686
CANONICAL_SHA=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_BYTES=225699
CALL_ARGUMENT_FOCUSED_TESTS=PASS; 23 PASSED
SEMANTIC_EVENT_SPINE_TESTS=PASS; ALL EXECUTED CASES PASSED; NATIVE-ONLY CASES SKIPPED
NATIVE_V_REPLAY=PASS; NATIVE-ONLY CASES SKIPPED
HISTORICAL_CALL_CLOSURE=RESCOPED_PASS; 656 CALLS; 736 ARGUMENTS; SOURCE 20FDDBB...; 166984 BYTES
CURRENT_CALL_MODEL=752 CALLS; 831 ARGUMENTS; MAX ARITY 4; DEPTH 2; NO UNCLOSED CALLS
CURRENT_CALL_CAPACITY=BLOCKED; CALL HEADROOM -22; ARGUMENT HEADROOM -85; FRESH NATIVE CLOSURE REQUIRED
PARAMETER_TRANSFORM=NOT_APPLICABLE_HISTORICAL_PARAMETER_TRANSFORM; STALE ANCHORS NOT REAPPLIED
BLOCK_CAPACITY=STATIC_BLOCK_CAPACITY_DESIGN_PASS; CURRENT SOURCE STRUCTURAL GUARDS PASS
BLOCK_PROJECTION=NATIVE_NOT_APPLICABLE; HISTORICAL PARAMETER PROJECTION NOT SYNTHESIZED
F3_F4_MIXED_NESTED_SUCCESSOR=NOT_PROVEN; FAIL_CLOSED_BEHAVIOR_PRESERVED
CANONICAL_MUTATED=NO
CANONICAL_REPROBE=NOT_RUN; CURRENT CALL CAPACITY GATE BLOCKED
SELF_EMIT=NOT_STARTED
STAGE1=NOT_STARTED
NEXT_SAFE_ACTION=obtain fresh native current-source call-argument closure or narrow the current source call model before any canonical reprobe; preserve historical snapshot classification
```

## Session Handoff 2026-08-29T23:41:03-03:00 - CURRENT CAPACITY AND SUCCESSOR CLOSURE

```text
CURRENT_CANDIDATE_SHA=1FC5ED99281938DF4FA4CC5D5513482BF7DCE986FFDFB7839883558C437BDED3
CURRENT_CANDIDATE_BYTES=811686
CURRENT_PHASE=PHASE_E_CANONICAL_FIRST_LOSS_CONVERGENCE

CAPACITY_SEMANTICS=752 and 831 are total CALL/A records accumulated by the current canonical scan; the fixed banks retain records for later verification and downstream consumers; a separate maximum-live measurement does not exist
CALL_TOTAL_COUNT=752
CALL_MAX_LIVE_COUNT=UNKNOWN
ARGUMENT_TOTAL_COUNT=831
ARGUMENT_MAX_LIVE_COUNT=UNKNOWN

CALL_CAPACITY_LIMIT=730
CALL_CAPACITY_CLASS=FIXED_RESIDENT_BUFFER_LIMIT
CALL_CAPACITY_OWNER=selfhost/compiler/s3c_stage1.s3; two metadata banks of 365 slots; ir_call_count < 730 at call registration
CALL_CAPACITY_CONSUMERS=call metadata writes; instruction call records; active-call references; verifier loop
CALL_CAPACITY_STATUS=BLOCKED_CURRENT_CANONICAL_TOTAL_EXCEEDS_FIXED_METADATA_BANKS; required 752; available 730; overflow sets ir_capacity_ok=0

ARGUMENT_CAPACITY_LIMIT=746
ARGUMENT_CAPACITY_CLASS=FIXED_RESIDENT_BUFFER_LIMIT
ARGUMENT_CAPACITY_OWNER=selfhost/compiler/s3c_stage1.s3; argument banks 365 + 365 + 16; ir_call_arg_pool_count < 746 at argument storage
ARGUMENT_CAPACITY_CONSUMERS=CALL C/A start/count metadata; argument value writes; verifier absolute-range checks; downstream record consumers
ARGUMENT_CAPACITY_STATUS=BLOCKED_CURRENT_CANONICAL_TOTAL_EXCEEDS_FIXED_ARGUMENT_BANKS; required 831; available 746; overflow sets argument_possible=0 and ir_capacity_ok=0; verifier requires pool count < 747

CAPACITY_BOUNDARY_TESTS=PASS; noncanonical call counts 729/730/731 map to below/at/above; noncanonical argument counts 745/746/747 map to below/at/above; above-limit model reports fits=false; source overflow is fail-closed
CAPACITY_ARCHITECTURAL_BLOCKER=YES
CAPACITY_OPTIONS=bounded general bank/chunk/replay representation or a separately qualified representation change; no arbitrary limit increase

FRESH_NATIVE_CLOSURE_REQUIRED=YES
NATIVE_CLOSURE_REQUIRED_GATES=current-source Linux x86-64 CALL/C/A closure and fresh native candidate/self-source verification
FRESH_NATIVE_CLOSURE_STATUS=UNAVAILABLE_ON_CURRENT_HOST
FULL_NATIVE_GATE_HOST_REQUIREMENT=Linux x86-64 with cc/gcc/clang; repository policy does not treat Windows execution as native closure
CURRENT_HOST_CAN_SATISFY=NO_FOR_THIS_CHECKPOINT
NATIVE_V_REPLAY=PASS; not equivalent to FULL_NATIVE_CANDIDATE_BUILD

F1=PASS
F2=PASS
F3=NOT_PROVEN; strict nested-match-in-arm with outer-arm continuation remains fail-closed in candidate V3 for the mutable noncanonical probe
F4=NOT_PROVEN; the passing adjacent loop/match fixtures do not jointly prove MATCH_SUCCESSOR, LOOP_BACKEDGE, LOOP_EXIT, and BREAK_TARGET for one candidate fixture
F5=PASS; existing nested-match-call-while-continuation hosted/candidate focused regression remains green

CALL_STATUS=PASS; current focused structural tests preserve call identity and bounded call model
C_STATUS=PASS; call metadata shape preserved
A_STATUS=PASS; argument order and bounded pool shape preserved
C_A_STATUS=PASS; candidate continuation regression preserves C/A records
I_CALL=PASS
O_OPERANDS=PASS
R_RESULTS=PASS
C_METADATA=PASS
A_ARGUMENT_ORDER=PASS

FOCUSED_CAPACITY_TESTS=PASS; 23 prior CALL/C/A and block-capacity tests plus 6 boundary cases
FOCUSED_SUCCESSOR_TESTS=PASS; selected nested_match_call_while/fallthrough set; 5 collected tests
AUDITOR_MODULE_MODE=PASS; current-source status emitted without reapplying stale parameter transform
CANONICAL_SHA=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_BYTES=225699
CANONICAL_MUTATED=NO
CANONICAL_REPROBE=NOT_RUN; capacity architectural blocker remains open
HOSTED_PARSE=PASS_FOR_NONCANONICAL_PROBES
HOSTED_SEMANTIC=PASS_FOR_NONCANONICAL_PROBES
HOSTED_LOWERING=PASS_FOR_EXISTING_F5_AND_ADJACENT_PROBES; strict F3 candidate probe remains fail-closed
S1_2=OPEN_BLOCKED
S1_6=DEFERRED
SELF_EMIT=NOT_STARTED
STAGE1=NOT_STARTED
T4=NOT_RUN
DIFF_CHECK=PASS

LAST_COMPLETED_GATE=CAPACITY_SEMANTICS_IDENTIFIED; NONCANONICAL_CAPACITY_BOUNDARIES_PASS; F5_SUCCESSOR_REGRESSION_PASS
FIRST_OPEN_GATE=CAPACITY_ARCHITECTURAL_CLOSURE_AND_STRICT_F3_F4_GENERALIZATION
NEXT_SAFE_ACTION=design a bounded chunk/replay or separately qualified representation change for current canonical CALL/A totals; retain fail-closed behavior and do not run canonical reprobe until capacity and F3/F4 are genuinely closed
```

## Checkpoint 2026-08-30T00:06:00-03:00 - BOUNDED C/A STREAM AND REPLAY PROOF

```text
CANDIDATE_SOURCE_PATH=selfhost/compiler/stage1_semantic_event_spine.s3
CANDIDATE_SOURCE_SHA256=1FC5ED99281938DF4FA4CC5D5513482BF7DCE986FFDFB7839883558C437BDED3
CANDIDATE_SOURCE_BYTES=811686
CANONICAL_INPUT_SOURCE_PATH=selfhost/compiler/s3c_stage1.s3
CANONICAL_INPUT_SOURCE_SHA256=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_INPUT_SOURCE_BYTES=225699
PHASE=PHASE_A_BOUNDED_CALL_A_RESIDENCY

CAPACITY_ARCHITECTURE=STREAMED_DIRECT_C_A_EMISSION_WITH_THREE_PASS_SCALAR_REPLAY
RESIDENT_BOUND=C_A_RECORDS_RETAINED_IN_CANDIDATE=0; scope is emitted C/A records only, not global compiler memory
SUMMARY_BOUND=SCALAR_SCAN_STATE_ONLY; no global O(1) or global bounded-memory claim
REPLAY_MODEL=PASS_0_VALIDATION; PASS_1_V_AND_BINDING_STREAM; PASS_2_V3_DIRECT_C_A_I_O_R_T_STREAM
HOST_CAPABILITY_REQUIREMENT=HOSTED_EMULATOR_FOR_FOCUSED_PROOF; LINUX_X86_64_NATIVE_REQUIRED_FOR_FRESH_NATIVE_CLOSURE
FAIL_CLOSED_CONDITIONS=NEGATIVE_SCAN_RESULT; UNSUPPORTED_C_A_SHAPE; CORE_V3_SUBSET_FALSE; MISSING_STREAM_COMPLETION

CALL_DECLARATION=NO_RESIDENT_CALL_BANK_IN_CANDIDATE; emit_v3_c writes one record at production
CALL_FIELDS=INSTRUCTION_ID; CALLEE_FUNCTION_ID; CALLEE_KIND; NAME_START; NAME_LENGTH
CALL_WRITERS=DIRECT_CALL_SITES_IN_SCAN_ROUTINES
CALL_READERS=STREAM_CONSUMERS_ONLY; NO_LATE_RANDOM_ACCESS_IN_CANDIDATE
CALL_REGENERATION=YES; deterministic source replay regenerates instruction and call identity
A_DECLARATION=NO_RESIDENT_ARGUMENT_BANK_IN_CANDIDATE; emit_v3_a writes one record at production
A_FIELDS=INSTRUCTION_ID; ARGUMENT_ORDINAL; VALUE_ID
A_WRITERS=DIRECT_ARGUMENT_SITES_IN_SCAN_ROUTINES
A_READERS=STREAM_CONSUMERS_ONLY; NO_LATE_RANDOM_ACCESS_IN_CANDIDATE
A_REGENERATION=YES; deterministic source replay regenerates argument order and value identity

LATE_VERIFICATION=C_A_TO_I=LOCAL_TO_CALL; A_TO_V=LOCAL_TO_CALL; O_R_TO_V=LOCAL_TO_INSTRUCTION; CALLEE_AND_RESULT_IDENTITY=LOCAL_TO_CALL; FUNCTION_AND_BLOCK_OWNERSHIP=GLOBAL_STREAM_INVARIANT
REPLAY_IDENTITY=FUNCTION_ID_STABLE; BLOCK_ID_STABLE_WHEN_SUPPORTED; INSTRUCTION_ID_STABLE; VALUE_ID_STABLE; CALL_ORDER_STABLE; ARGUMENT_ORDER_STABLE
ATOMIC_CALL_UNIT=CALL_RECORD_AND_ALL_ARGUMENT_RECORDS_EMITTED_AS_ONE_SCANNER_ACTION; MAX_ARGUMENTS_PROVEN_BY_FIXTURE=3; unsupported shapes fail closed

NONCANONICAL_STREAM_TESTS=PASS; one-argument, three-argument, discard-call C/A streams close I/V references and preserve ordinal order
REPLAY_DETERMINISM_TEST=PASS; repeated hosted candidate V3 stream is byte/record identical for three-argument call
SOURCE_RESIDENCY_TEST=PASS; no candidate call/argument record banks; scalar three-pass entrypoints present
CHUNK_BOUNDARY_TESTS=NOT_APPLICABLE_TO_SELECTED_DIRECT_STREAM_ARCHITECTURE; no chunk boundary is claimed or synthesized
TOTAL_CALL_MODEL_LIMIT=NOT_PROVEN_FOR_CANDIDATE; bounded C/A residency does not imply unlimited total source/ID model
TOTAL_ARGUMENT_MODEL_LIMIT=NOT_PROVEN_FOR_CANDIDATE; bounded C/A residency does not imply unlimited total source/ID model

CURRENT_CANONICAL_CALL_TOTAL=752
CURRENT_CANONICAL_ARGUMENT_TOTAL=831
CURRENT_CANONICAL_CAPACITY=BLOCKED; canonical still uses fixed resident banks of 730 calls and 746 arguments
CURRENT_MODEL_SUPPORTED=NO; candidate direct-stream subset has not closed the current canonical semantic shape
CAPACITY_ARCHITECTURAL_BLOCKER=OPEN_FOR_CURRENT_CANONICAL; no arbitrary capacity increase and no canonical mutation

F1=PASS
F2=PASS
F3=NOT_PROVEN
F4=NOT_PROVEN
F5=PASS
FOCUSED_GATE=PASS; 138 focused cases collected and completed; native-only cases skipped on Windows
CALL_C_A_STRUCTURAL=PASS
NATIVE_V_REPLAY=PASS; existing focused hosted/native contract preserved; fresh current-source native closure unavailable on Windows
CANONICAL_PROBE=NOT_RUN; capacity and F3/F4 gates remain open
CANONICAL_MUTATED=NO
S1_2=OPEN_BLOCKED
S1_6=DEFERRED
SELF_EMIT=NOT_STARTED
STAGE1=NOT_STARTED
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
T4=NOT_RUN
DIFF_CHECK=PASS

LAST_COMPLETED_GATE=BOUNDED_DIRECT_C_A_STREAM_AND_REPLAY_FOCUSED_PASS
FIRST_OPEN_GATE=CURRENT_CANONICAL_CAPACITY_CLOSURE_AND_STRICT_F3_F4_GENERALIZATION
NEXT_SAFE_ACTION=close_current_canonical_capacity_and_strict_F3_F4_with_a_general_candidate_architecture; do_not_claim_current_752_831_support_from_subset_proof
```

## Checkpoint 2026-08-30T00:18:00-03:00 - STRICT MIXED-LOOP FAIL-CLOSED CANARY

```text
CANDIDATE_SOURCE_PATH=selfhost/compiler/stage1_semantic_event_spine.s3
CANDIDATE_SOURCE_SHA256=1FC5ED99281938DF4FA4CC5D5513482BF7DCE986FFDFB7839883558C437BDED3
CANDIDATE_SOURCE_BYTES=811686
CANONICAL_INPUT_SOURCE_SHA256=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_INPUT_SOURCE_BYTES=225699
PHASE=PHASE_B_SUCCESSOR_CONTEXT_CLOSURE

STRICT_NONCANONICAL_FIXTURE=MIXED_MATCH_IN_LOOP_SOURCE
HOSTED_REFERENCE=PASS; loop relation contains a real BRANCH3 and mixed terminal/fallthrough match arms
CANDIDATE_RESULT=FAIL_CLOSED; partial prefix contains no B/T/Z records and no incomplete CFG is accepted
FAIL_CLOSED_REGRESSION=PASS
F3=NOT_PROVEN; a general joined CFG context is still required for a mixed match nested inside a loop
F4=NOT_PROVEN; distinct match successor, loop backedge, loop exit, and break target are not jointly emitted by the candidate
F5=PASS

CANONICAL_PROBE=NOT_RUN; current canonical capacity and successor gates remain open
CANONICAL_MUTATED=NO
S1_2=OPEN_BLOCKED
S1_6=DEFERRED
SELF_EMIT=NOT_STARTED
STAGE1=NOT_STARTED
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
T4=NOT_RUN
DIFF_CHECK=PASS

LAST_COMPLETED_GATE=STRICT_MIXED_LOOP_FAIL_CLOSED_REGRESSION_PASS
FIRST_OPEN_GATE=GENERAL_JOINED_CFG_CONTEXT_AND_CURRENT_CANONICAL_CAPACITY_CLOSURE
NEXT_SAFE_ACTION=implement_or_prove_a_general_join_context_for_nested_mixed_matches; preserve_fail_closed_behavior_until_all_block_and_terminator_ownership_is_explicit
```

## Checkpoint 2026-08-30T00:27:00-03:00 - BOUNDED ARCHITECTURE WIRING AUDITED

```text
CANDIDATE_SOURCE_PATH=selfhost/compiler/stage1_semantic_event_spine.s3
CANDIDATE_SOURCE_SHA256=1FC5ED99281938DF4FA4CC5D5513482BF7DCE986FFDFB7839883558C437BDED3
CANDIDATE_SOURCE_BYTES=811686
CANONICAL_INPUT_SOURCE_PATH=selfhost/compiler/s3c_stage1.s3
CANONICAL_INPUT_SOURCE_SHA256=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_INPUT_SOURCE_BYTES=225699
PHASE=PHASE_A_CAPACITY_WIRING_AUDIT

BOUNDED_ARCHITECTURE_IMPLEMENTED_IN_CANDIDATE=YES; direct C/A output plus three scalar replay passes
OLD_CALL_BANK_STILL_EXISTS=NO_IN_CANDIDATE; YES_IN_UNCHANGED_CANONICAL
OLD_ARGUMENT_BANK_STILL_EXISTS=NO_IN_CANDIDATE; YES_IN_UNCHANGED_CANONICAL
CALL_730_CURRENT_MEANING=CANONICAL_RESIDENT_CALL_METADATA_SLOTS; two 365-slot banks, not a candidate chunk size
ARG_746_CURRENT_MEANING=CANONICAL_RESIDENT_ARGUMENT_POOL_SLOTS; 365+365+16 slots, not a candidate chunk size
CURRENT_CAPACITY_FAILURE_OWNER=selfhost/compiler/s3c_stage1.s3 write/verifier guards, mirrored by the static current-source auditor
CANDIDATE_SOURCE_ACTUALLY_CHANGED=NO

PHYSICAL_RESIDENT_CAPACITY_CANDIDATE=C_A_RECORD_RETENTION=0; direct write at production point
TOTAL_SUPPORTED_MODEL_COUNT_CANDIDATE=NOT_PROVEN; scalar IDs/counters and semantic coverage are not a total-capacity proof
CURRENT_CANONICAL_CALL_TOTAL=752
CURRENT_CANONICAL_ARGUMENT_TOTAL=831
CURRENT_CANONICAL_CALL_TOTAL_SUPPORTED=NO; current canonical still requires 752 <= 730 and fails closed
CURRENT_CANONICAL_ARGUMENT_TOTAL_SUPPORTED=NO; current canonical still requires 831 <= 746 and fails closed
MEASURED_CALL_RESIDENT_MAX=0_FOR_C_A_RECORDS_IN_CANDIDATE
MEASURED_ARG_RESIDENT_MAX=0_FOR_C_A_RECORDS_IN_CANDIDATE

CAPACITY_WIRING_STATUS=PARTIAL; candidate route is present, but it is not wired to or proven against the current canonical semantic model
CANONICAL_PROBE=NOT_RUN
CANONICAL_MUTATED=NO
F3=NOT_PROVEN
F4=NOT_PROVEN
F5=PASS
S1_2=OPEN_BLOCKED
S1_6=DEFERRED
SELF_EMIT=NOT_STARTED
STAGE1=NOT_STARTED
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
T4=NOT_RUN
DIFF_CHECK=PASS

LAST_COMPLETED_GATE=BOUNDED_ARCHITECTURE_WIRING_AUDITED
FIRST_OPEN_GATE=GENERAL_CURRENT_CANONICAL_CAPACITY_WIRING_AND_F3_F4_CFG_GENERALIZATION
NEXT_SAFE_ACTION=qualify a general candidate capacity and CFG route without mutating canonical; retain fail-closed behavior while current canonical support is unproven
```

## Checkpoint 2026-08-30T02:43:56-03:00 - F3/F4 FOCUSED CLOSURE AND HOSTED PROBE BOUNDARY

```text
CANDIDATE_SOURCE_PATH=selfhost/compiler/stage1_semantic_event_spine.s3
CANDIDATE_SOURCE_SHA256=DF64B9164BE22D6E0A45ECAC3A72123876C012C0E5F0CFF8A0AA6038E3400F06
CANDIDATE_SOURCE_BYTES=877596
CANONICAL_INPUT_SOURCE_PATH=selfhost/compiler/s3c_stage1.s3
CANONICAL_INPUT_SOURCE_SHA256=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_INPUT_SOURCE_BYTES=225699
PHASE=PHASE_B_SUCCESSOR_CONTEXT_CLOSURE

CAPACITY_ARCHITECTURE=PARTIAL; candidate has direct C/A emission with scalar replay and no resident C/A banks; total canonical model support is not proven
TARGET_PARAMETER_CAPACITY=PASS; global 64 accepted and 65 rejected closed
MEASURED_CALL_RESIDENT_MAX=0_FOR_C_A_RECORDS_IN_CANDIDATE
MEASURED_ARG_RESIDENT_MAX=0_FOR_C_A_RECORDS_IN_CANDIDATE
CURRENT_CANONICAL_CALL_TOTAL=752
CURRENT_CANONICAL_ARGUMENT_TOTAL=831
CURRENT_CANONICAL_TOTAL_MODEL_SUPPORTED=NOT_PROVEN_IN_CANDIDATE

F1=PASS
F2=PASS
F3=PASS; nested successor and outer continuation focused contract
F4=PASS; dynamic mixed, literal mixed, and break-target focused contracts
F5=PASS
FOCUSED_EVENT_SPINE=PASS; full focused file completed with expected skips
ADJACENT_EMITTER_CALL_TESTS=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS

CANONICAL_PROBE=INCOMPLETE; hosted prefix F=10 V=138 D=18 I=213 C=6 A=6 O=148 R=124 T=76 B=74 M=6 and no Z completion
CANONICAL_MUTATED=NO
CANONICAL_SEMANTIC_CONFORMANCE=NOT_PROVEN
S1_2=OPEN_BLOCKED
S1_6=DEFERRED
SELF_EMIT=FAIL_CLOSED; candidate-on-candidate hosted attempt produced only F/V/D and no completed V3 stream
STAGE1=NOT_STARTED
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
T4=NOT_RUN

LAST_COMPLETED_GATE=F3_F4_F5_FOCUSED_PASS_AND_HOSTED_PROBE_BOUNDARY
FIRST_OPEN_GATE=CANONICAL_SEMANTIC_CONFORMANCE_AND_TOTAL_MODEL_CAPACITY
NEXT_SAFE_ACTION=extend the candidate only with a bounded general emitter path that closes canonical semantic coverage; retain fail-closed self-emit boundary and do not start Stage2/Stage3
```

## Checkpoint 2026-08-31 - FAST ITERATION AND SEMANTIC STANDARDIZATION BASELINE

```text
CANDIDATE_SOURCE_PATH=selfhost/compiler/stage1_semantic_event_spine.s3
CANDIDATE_SOURCE_SHA256=B77BAAF8B307BFB1163683919F8B43784A3B4B8470259471656C8CE62A0DB28A
CANDIDATE_SOURCE_BYTES=1224207
CANONICAL_INPUT_SOURCE_PATH=selfhost/compiler/s3c_stage1.s3
CANONICAL_INPUT_SOURCE_SHA256=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_INPUT_SOURCE_BYTES=225699
CANONICAL_CURRENT_SHA=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_EXPECTED_SHA=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_GIT_STATUS=MODIFIED_INHERITED; identity remains exact and file was not touched in this phase
CANONICAL_CHANGED_DURING_THIS_PHASE=NO

PHASE=INFRASTRUCTURE_FAST_ITERATION_AND_SEMANTIC_STANDARDIZATION
FAST_PROBE_CORE=PASS
COMPILE_CACHE_IDENTITY=PASS; raw source SHA plus optimization and SyntaxMode value form CandidateCacheKey
IR_REUSE_SAFETY=PASS; digest before/after equal; cold and reused records equal
EXECUTION_STATE_ISOLATION=PASS; SourceResourceRuntime, output/error buffers, and I/O hook are fresh per run
SEMANTIC_REGISTRY_LOAD=PASS
REGISTRY_DETERMINISM=PASS; canonical JSON uses sorted object keys and rules normalize by sorted rule_id
LANGUAGE_QUERY_BASIC=PASS
REGISTRY_RULESET_SHA256=81536D1AEFB8F8887D084F852F63C367D102AE52A0D395C9F8F37DDB92E6E565
FOCUSED_INFRASTRUCTURE_TESTS=PASS; 7 passed
REAL_REUSE_TIMINGS=PASS; one compile 49.0615s; five noncanonical fixtures; all cold/reused outputs equal
REAL_FIXTURES=smoke, mutable, call, match, nested-match-while

HOSTED_PARSE_SEMANTIC_LOWERING=PASS_FOR_INFRASTRUCTURE_CANARIES
NATIVE_BUILD=NOT_RUN_IN_THIS_PHASE
CANONICAL_PROBE=DEFERRED; explicitly prohibited until infrastructure closure
CANONICAL_MUTATED=NO
S1_2=OPEN_BLOCKED
S1_6=DEFERRED
SELF_EMIT=NOT_STARTED
STAGE1=NOT_STARTED
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
T4=NOT_RUN
DIFF_CHECK=PASS

LAST_COMPLETED_GATE=FAST_PROBE_AND_SEMANTIC_REGISTRY_INFRASTRUCTURE_CLOSURE
FIRST_OPEN_GATE=RESUME_CANONICAL_SEMANTIC_LOSS_CONVERGENCE
NEXT_SAFE_ACTION=resume the bounded canonical semantic investigation only after this infrastructure checkpoint; preserve canonical identity and fail-closed behavior
```

## Checkpoint 2026-08-31T15:15:39-03:00 - MIXED CONTINUATION AND CANONICAL REPROBE

```text
PHASE=PHASE_E_CANONICAL_FIRST_LOSS_CONVERGENCE
SEMANTIC_VALUE_TYPE=resolved_by_candidate_semantic_registry; i64/trit/tryte type contracts remain distinct
CONTROL_EFFECT=return_is_arm_terminal; discard_is_nonterminal_fallthrough; enclosing successor remains lexical
LOWERING_RESULT_KIND=shared_decoder; plain=0; cursor_continuation=1; terminal=2; block_continuation=3
NEXT_CURSOR=decoded_by_lowering_result_next_cursor
NEXT_BLOCK=decoded_by_lowering_result_next_block_for_block_continuation
OUTER_SUCCESSOR=preserved_as_the_decoded_successor_block_and_emitted_lexical_followup

CANDIDATE_SOURCE_PATH=selfhost/compiler/stage1_semantic_event_spine.s3
CANDIDATE_SOURCE_SHA256=3BD6E1F1E051BD0D7AF2648C7C26189FB999874E870EFAEA8BEABD32314CEA91
CANDIDATE_SOURCE_BYTES=1226682
CANONICAL_INPUT_SOURCE_PATH=selfhost/compiler/s3c_stage1.s3
CANONICAL_INPUT_SOURCE_SHA256=44F022820A9191E3A6D402C188EB4B242E0FFEEFD7A149B15E2B46039031B9CB
CANONICAL_INPUT_SOURCE_BYTES=225699
CANONICAL_CHANGED_DURING_THIS_PHASE=NO

FAST_PROBE_CORE=PASS
COMPILE_CACHE_IDENTITY=PASS
IR_REUSE_SAFETY=PASS
EXECUTION_STATE_ISOLATION=PASS
SEMANTIC_REGISTRY_LOAD=PASS
REGISTRY_DETERMINISM=PASS
LANGUAGE_QUERY_BASIC=PASS
TIER2_CONTINUATION_REGRESSION=PASS
MIXED_CONTINUATION_FIXTURE=PASS
NEGATIVE_ARM_TERMINAL=PASS
NEUTRAL_ARM_FALLTHROUGH=PASS
POSITIVE_ARM_TERMINAL=PASS
OUTER_SUCCESSOR_RESTORED=PASS
NO_DUPLICATE_TERMINATOR=PASS
REFERENTIAL_INTEGRITY=PASS
COLD_REUSED_OUTPUT_EQUAL=PASS
IR_DIGEST_UNCHANGED=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS

CANONICAL_PROBE_RUN=YES_EXACTLY_ONE
CANONICAL_PROBE_TRANSCRIPT=scratch/canonical-v3-reprobe-20260831-after-continuation-protocol.txt
CANONICAL_PROBE_EXIT=0
CANONICAL_RECORD_COUNTS=F10,B123,D20,V238,M11,I386,O254,R223,C15,A19,T131,Z0
FIRST_LOSS=CANONICAL_STREAM_INCOMPLETE_AFTER_LAST_EMITTED_FUNCTION; function=scan_token; construct=loop_continuation
DIAGNOSTIC_CODE=S3IR2_CANONICAL_STREAM_INCOMPLETE
RULE_ID=S3.CONTROL.MATCH_THREE_WAY
CANONICAL_CONFORMANCE=OPEN_BLOCKED; completion record Z absent
S1_2=OPEN_BLOCKED
S1_6=DEFERRED
SELF_EMIT=NOT_STARTED
STAGE1=NOT_STARTED
CANONICAL_MUTATED=NO
NEXT_SAFE_ACTION=continue semantic generalization from the diagnosed canonical loop-continuation loss; no additional canonical probe in this checkpoint
```

## Checkpoint 2026-09-01T16:59:58-03:00 - FROZEN CANDIDATE PROBE

```text
S3_STAGE1_PROVENANCE_RECOVERY=COMPLETE
BRANCH=recovery/pr268-stage1-streaming-values-20260828
HEAD=1ec76af89992f119865a370488593ad5c85c4c49

CANONICAL_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
CANONICAL_BYTES=225699
CANONICAL_MUTATION=NO

CANDIDATE_PATH=selfhost/compiler/stage1_semantic_event_spine.s3
CANDIDATE_ABSOLUTE_PATH=C:\Users\samue\Downloads\S3\S3-PR268-Stage1-Streaming\selfhost\compiler\stage1_semantic_event_spine.s3

LIVE_OBSERVATION_1_SHA=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6
LIVE_OBSERVATION_1_SIZE=1334057
LIVE_OBSERVATION_1_CREATION_UTC=2026-08-29T01:42:36.7124071Z
LIVE_OBSERVATION_1_MTIME_UTC=2026-09-01T19:34:35.4008049Z
LIVE_OBSERVATION_2_SHA=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6
LIVE_OBSERVATION_2_SIZE=1334057
LIVE_OBSERVATION_2_CREATION_UTC=2026-08-29T01:42:36.7124071Z
LIVE_OBSERVATION_2_MTIME_UTC=2026-09-01T19:34:35.4008049Z
LIVE_OBSERVATION_3_SHA=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6
LIVE_OBSERVATION_3_SIZE=1334057
LIVE_OBSERVATION_3_CREATION_UTC=2026-08-29T01:42:36.7124071Z
LIVE_OBSERVATION_3_MTIME_UTC=2026-09-01T19:34:35.4008049Z
STABLE_60S=YES

WRITER_IDENTIFIED=NO
WRITER_PID=NOT_OBSERVED
WRITER_PARENT=NOT_OBSERVED
WRITER_COMMAND=NOT_OBSERVED
WRITER_CLASSIFICATION=NO_ACTIVE_WRITER_DURING_STABILITY_WINDOW; prior mutator was not present for attribution
STALE_LOCK=.s3-stage1-autonomous.lock PID=11180; PID_NOT_RUNNING
READ_ONLY_DIAGNOSTIC_PID=560; ended before probe

SNAPSHOT_PATH=reports/selfhost/stage1/provenance/20260901T164008/candidate.snapshot
SNAPSHOT_SHA256=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6
SNAPSHOT_BYTES=1334057
SNAPSHOT_READONLY=YES
LIVE_SHA_BEFORE_COPY=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6
LIVE_SIZE_BEFORE_COPY=1334057
LIVE_SHA_AFTER_COPY=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6
LIVE_SIZE_AFTER_COPY=1334057
SNAPSHOT_COPY_MATCH=YES

PROBE_EXECUTED=YES
PROBE_COUNT=1
PROBE_COMMAND=python tools/stage1_fast_probe.py --candidate reports/selfhost/stage1/provenance/20260901T164008/candidate.snapshot --canonical-summary
PROBE_INPUT_SHA256=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6
PROBE_PRE_HASH=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6
PROBE_POST_HASH=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6
PROBE_HASH_MATCH=YES
PROBE_EXIT=0
PROBE_START=2026-09-01T16:40:46-03:00
PROBE_END=2026-09-01T16:59:58-03:00

COUNTS=F10,B143,D21,V291,M12,I459,O309,R275,C25,A36,T149,Z0
F=10
B=143
D=21
V=291
M=12
I=459
O=309
R=275
C=25
A=36
T=149
Z=0
FIRST_LOSS=scan_token / completion record Z absent
DIAGNOSTIC_CODE=S3IR2_CANONICAL_STREAM_INCOMPLETE
RULE_ID=S3.CONTROL.MATCH_THREE_WAY
FUNCTION_BOUNDARY_CROSSED=NO
CANONICAL_PROGRESS=YES

POST_PROBE_LIVE_SHA=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6
LIVE_MATCHES_PROBED_SNAPSHOT=YES
MIXED_PROVENANCE=NO
PROBE_RESULT_APPLIES_TO_SHA256=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6

S1_2=OPEN
COMMIT=NO
PUSH=NO
NEXT_SAFE_ACTION=do not fix the parser in this task; investigate the diagnostic against this exact frozen snapshot in a later task
```

## Checkpoint 2026-09-01T17:17:20-03:00 - S1.2 Z COMPLETION LOSS ANALYSIS

```text
ANALYSIS_INPUT=snapshot
SNAPSHOT_SHA256=6a611595775efc17b1744d3fccdfc9449d0393dba37496e8b9275f2e5ca237c6
SNAPSHOT_BYTES=1334057
CANONICAL_SHA256=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
CANONICAL_MUTATION=NO
LIVE_CANDIDATE_MUTATION=NO_DURING_PROBE

RECORD_ALPHABET=F,B,D,V,M,I,O,R,C,A,T,Z
Z_SEMANTICS=stream-level S3IR2 v3 completion record; serialized as Z 15\\n
Z_PRODUCER_FUNCTION=emit_v3_complete
Z_PRODUCER_LOCATION=snapshot:359
Z_PRODUCER_IMPLEMENTATION=emit_v3_char(90), emit_v3_field(15), emit_v3_char(10)
Z_PRODUCER_CALLSITE=snapshot:23135
Z_PRODUCER_CALLSITE_OWNER=main

EXPECTED_Z_PRODUCTION_PATH=main -> scan_program(0,0) -> scan_program(1,0) -> core_v3_subset() -> emit_v3_header() -> scan_program(2,0) -> emit_v3_complete() -> s3_stage1_exit(0)
Z_GATES=main entry; validated_count >= 0; host_count >= 0; complete_count >= 0; core_v3_subset() == -1; v3_count >= 0
SCAN_PROGRAM_EOF=snapshot:22995-23017; loop exits at cursor >= length, may emit final B, then returns next_id; it does not emit Z

PROBE_PATH=stage1_fast_probe.main:331 -> get_cached_candidate -> Stage1Candidate.run_file:148 -> run_stream:102 -> _execute_function(scan_program, (2,0)):138 -> _parse_v3_stream:25 -> _record_counts:199 -> _canonical_diagnostic:204
PROBE_ENTRYPOINT=scan_program directly
PROBE_BYPASSES=main and its completion gates/call to emit_v3_complete
Z_PRODUCER_REACHED_IN_PROBE=NO
Z_APPENDED_IN_PROBE=NO
Z_SERIALIZED_IN_PROBE=NO
Z_PARSED_IN_PROBE=NO
Z_COUNTED_IN_PROBE=NO

STATIC_FIRST_DIVERGENCE=Stage1Candidate.run_stream calls candidate scan_program directly instead of candidate main; main is never entered, so emit_v3_complete is unreachable for this probe
CLASSIFICATION=CASE_A_PRODUCER_NEVER_REACHED
ROOT_CAUSE=probe entrypoint/contract mismatch, not parser loss and not proven candidate EOF corruption
FIRST_EXACT_LOSS=run_stream -> scan_program direct entry; expected main -> scan_program -> emit_v3_complete boundary is bypassed

KNOWN_GOOD_Z_FIXTURE=tests/test_stage1_semantic_event_spine.py:test_native_v3_const_return_is_lossless_and_not_literal_specific
KNOWN_GOOD_Z_LOCATION=tests/test_stage1_semantic_event_spine.py:1503-1528
KNOWN_GOOD_Z_INLINE_SOURCE_SHA256=d950b6e8711edd1c31d898dbfa4d02219a972d7454ff99cb4b67e10c0a4ce6ac
KNOWN_GOOD_Z_COUNT=1; test asserts records["Z"] == [(15,)] after native executable entry

PROBE_FALSE_NEGATIVE_POSSIBLE=NO_FOR_VALID_SERIALIZED_Z
PROBE_FALSE_NEGATIVE_REASON=_parse_v3_stream accepts arbitrary record tags including Z; splitlines handles LF/CRLF and missing final newline; _record_counts includes Z; malformed ASCII/numeric input raises rather than silently producing Z=0
INPUT_TRUNCATED=NO
INPUT_TRUNCATION_EVIDENCE=snapshot UTF-8 valid; final byte LF; final non-empty source line is complete return 2

INSTRUMENTATION_REQUIRED=NO
DIAGNOSTIC_RUN_COUNT=0
FUNCTION_BOUNDARY_CROSSED=NO; no candidate producer/consumer defect; harness bypass is proven statically
S1_2=OPEN
COMMIT=NO
PUSH=NO
NEXT_FIX_SHOULD_TARGET=the canonical-summary diagnostic contract/entrypoint; either invoke candidate main in a separately qualified end-to-end probe or remove Z as a criterion from direct scan_program summaries
```

## Checkpoint 2026-09-03T15:33:41-03:00 - BUILTIN RETURN CONVERSION / FUNCTION BOUNDARY

```text
ANALYSIS_INPUT=bounded noncanonical function-boundary canary after call-signature resolution
BRANCH=recovery/pr268-stage1-streaming-values-20260828
REPOSITORY_HEAD=1ec76af89992f119865a370488593ad5c85c4c49
CANDIDATE_SHA_BEFORE=94001e8b9b068a72757732fd89d2f25593ff84e57ffdc691ba68c9afb8fb3a54
CANDIDATE_SHA_AFTER=e50855cecad6dc81bec4da6a510dd34960d9530a59a9325ee38418e76126ac5d
CANDIDATE_BYTES_AFTER=1366637
CANONICAL_SHA256=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
CANONICAL_BYTES=225699
CANONICAL_MUTATED=NO

FIRST_DIVERGENT_FIELD=CALL_SIGNATURE; parse_call_return_type ignored builtin_call_signature
CALL_SIGNATURE_RESOLUTION=PASS; shared resolve_call_signature checks builtins then declared functions
BUILTIN_RETURN_LOWERING=PASS; conversion opcode 10 with typed operand and return terminator
MUTABLE_ARGUMENT_HANDLING=PASS; local mutable argument uses bounded index/load before conversion
FUNCTION_A_COMPLETES=YES
CURSOR_ADVANCES_TO_FUNCTION_B=YES
FUNCTION_B_F_EMITTED=YES
FUNCTION_MAIN_F_EMITTED=YES
PREMATURE_Z=NO
NO_DUPLICATE_TERMINATOR=PASS
REFERENTIAL_INTEGRITY=PASS
S1_2=OPEN
STAGE2=NOT_STARTED
COMMIT=NO
PUSH=NO

FOCUSED_BUILTIN_RETURN_CANARY=PASS
TIER0=PASS; 5 passed, 2 skipped
TIER1=PASS
TIER2=PASS; 62 passed
COMPILEALL=PASS
DIFF_CHECK=PASS
CANONICAL_REPROBE=AUTHORIZED_NEXT_ITERATION_ONLY
```

## Checkpoint 2026-09-02 - POST-LOOP SUCCESSOR / F10 DIVERGENCE RECONCILIATION

```text
ANALYSIS_INPUT=existing bounded generic trace plus noncanonical boundary canary; canonical reprobe not repeated
CANDIDATE_SHA256=2a8ec4674798adbe015abb609af8a8a7509812067557af29740645b323a3cbf6
CANDIDATE_BYTES=1356102
CANONICAL_SHA256=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
CANONICAL_BYTES=225699
CANONICAL_PROBE_THIS_TURN=NO

SCAN_TOKEN_F_EMITTED=YES
SCAN_TOKEN_BODY_LAST_SOURCE_CURSOR=UNAVAILABLE_FROM_BOUNDED_TRACE
SCAN_TOKEN_EXPECTED_BODY_STOP=7147 generic reproduction; 11174 canonical source
SCAN_TOKEN_BODY_STOP_REACHED=NO in the pre-fix generic reproduction
SCAN_TOKEN_FINAL_RESULT_RAW=-1
SCAN_TOKEN_FINAL_RESULT_KIND=INVALID
SCAN_TOKEN_FINAL_NEXT_CURSOR=UNAVAILABLE
SCAN_TOKEN_FINAL_NEXT_BLOCK=UNAVAILABLE
SCAN_TOKEN_FINAL_NEXT_ID=UNAVAILABLE
SCAN_TOKEN_COMPLETES=NO in the pre-fix generic reproduction
NEXT_FUNCTION_HEADER_EXPECTED=fn following(limit: i64) -> i64:
NEXT_FUNCTION_HEADER_CURSOR=7147 generic reproduction
NEXT_FUNCTION_HEADER_REACHED=NO in the pre-fix generic reproduction
NEXT_FUNCTION_F_EMITTER_REACHED=NO in the pre-fix generic reproduction
NEXT_FUNCTION_F_EMITTED=NO in the pre-fix generic reproduction

FIRST_DIVERGENT_FIELD=LOWERING_RESULT_KIND at nested call-relation condition dispatch
FIRST_DIVERGENT_CURSOR=4909 generic reproduction
FIRST_DIVERGENT_SOURCE_TEXT=match read_at(position + 1) == 61:
FIRST_DIVERGENT_DISPATCHER=scan_match_line_context(mode=2)
FIRST_DIVERGENT_HELPER=scan_match_call_relation_terminal_return_v3 unsupported nested-negative shape; fallback scan_match_nested_match_body_v3
FAILURE_FAMILY=MATCH_CONDITION
FUNCTION_BOUNDARY_DIAGNOSIS=not the primary pre-fix loss; the body failed before completion

Z_EMISSION_ATTEMPTED=NO
Z_EMISSION_PRECONDITION=main entry plus finalization gates
Z_EMISSION_RESULT=NOT_ATTEMPTED by the direct scan_program probe
DIAGNOSTIC_SCOPE=the prior S3IR2_CANONICAL_STREAM_INCOMPLETE summary is coarse when the direct probe bypasses main; it cannot distinguish a body lowering failure from program finalization

NESTED_CALL_RELATION_BOUNDARY_CANARY=PASS
FUNCTION_A_COMPLETES=YES
CURSOR_ADVANCES_TO_FUNCTION_B=YES
FUNCTION_B_F_EMITTED=YES
PREMATURE_Z=NO
PROGRAM_FINAL_Z_AFTER_LAST_FUNCTION=NOT_EXERCISED_BY_DIRECT_CANARY
POST_LOOP_SUCCESSOR_FIX=PASS
MAIN_LITERAL_RETURN_VALIDATION_FIX=PASS
TIER0=PASS
TIER1_CURRENT_CANDIDATE=PASS
TIER2_CONTINUATION_REGRESSION=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS

S1_2=OPEN
COMMIT=NO
PUSH=NO
CANONICAL_MUTATION=NO
NEXT_SAFE_ACTION=await an explicitly authorized single canonical qualification after the current local gates; do not use canonical as a debugger
```

## Checkpoint 2026-09-04 - GENERIC MUTABLE BINARY ASSIGNMENT / CANONICAL REPROBE

```text
ANALYSIS_INPUT=generic decimal pipeline canary plus one authorized canonical reprobe
SOURCE_FIX=generic mutable binary assignment lowering with shared instruction-count accounting
CANONICAL_PROBE_TRANSCRIPT=scratch/canonical-v3-reprobe-20260904-binary-assignment.txt
CANONICAL_PROBE_START=2026-09-04T04:00:11.2823298-03:00
CANONICAL_PROBE_END=2026-09-04T11:26:48.4273359-03:00
CANONICAL_PROBE_EXIT=0

GENERIC_DECIMAL_PIPELINE_BOUNDARY_CANARY=PASS
TIER0=PASS; 5 passed, 2 skipped
TIER1=PASS; 62 passed
TIER2=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS

CANONICAL_COUNTS=F=23 B=457 D=46 V=1901 M=16 I=2374 O=1406 R=1866 C=633 A=682 T=463 Z=0
FIRST_LOSS={"after_function":"emit_ir_return","condition":"completion record Z was not emitted"}
DIAGNOSTIC_CODE=S3IR2_CANONICAL_STREAM_INCOMPLETE
RULE_ID=S3.CONTROL.MATCH_THREE_WAY
CANONICAL_PROBE_SCOPE=direct scan_program probe; main/finalization is bypassed and Z=0 is not an EOF proof

CANONICAL_SHA_BEFORE=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
CANONICAL_SHA_AFTER=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
CANONICAL_BYTES_BEFORE=225699
CANONICAL_BYTES_AFTER=225699
CANONICAL_MUTATION=NO
CANDIDATE_SHA_BEFORE=82c9cd4a973eefccf4149231ca84b16174a287611a5aae72c26564b01cc88dfd
CANDIDATE_SHA_AFTER=82c9cd4a973eefccf4149231ca84b16174a287611a5aae72c26564b01cc88dfd

BOUNDARY_CLASSIFICATION=generic assignment boundary fixed; canonical direct-probe Z diagnostic remains harness-scoped and coarse
S1_2=OPEN
STAGE2=NOT_STARTED
COMMIT=NO
PUSH=NO
CANONICAL_PROBE_RERUN_REQUIRED=NO within this checkpoint
```

## Checkpoint 2026-09-04 - PHASE 1 PROBE COST INFRASTRUCTURE

```text
PROBE_COST_OPTIMIZATION_STATUS=PHASE1_IMPLEMENTED
DIAGNOSTIC_MODE=SUPPORTED
MILESTONE_MODE=SUPPORTED; explicit --stop-after-f
QUALIFICATION_MODE=DEFAULT_CANONICAL_SUMMARY_PRESERVED
DEFAULT_QUALIFICATION_BEHAVIOR_PRESERVED=YES
PROGRESS_FUNCTIONS_AVAILABLE=YES; stderr only
COMPILED_CANDIDATE_REUSE=YES; source SHA plus optimization plus mode cache key
IR_REUSE_SAFETY=PASS; existing digest and fresh-runtime gates preserved
DEVELOPMENT_FRONTIER_F=23
FULL_QUALIFICATION_FRONTIER_F=23
LAST_MILESTONE_TARGET=24
LAST_MILESTONE_RESULT=NOT_RUN
LAST_MILESTONE_SECONDS=UNAVAILABLE
LAST_FULL_QUALIFICATION_SECONDS=26746.298213100003
COST_DOMINANT_PHASE=UNMEASURED_FOR_MILESTONE; instrumentation now available
FOCUSED_INFRASTRUCTURE_TESTS=PASS; 6 passed
COMPILEALL=PASS
DIFF_CHECK=PASS
CANONICAL_MUTATION=NO
COMMIT=NO
PUSH=NO
STAGE2=NOT_STARTED
NEXT_SAFE_ACTION=run one canonical-start milestone probe with TARGET_F=24
```

## Checkpoint 2026-09-04 - MILESTONE F24 ATTEMPT

```text
PROBE_MODE=MILESTONE
MILESTONE_TRANSCRIPT=scratch/stage1-milestone-f24-20260904.txt
MILESTONE_TARGET_F=24
MILESTONE_REACHED=NO
F_OBSERVED=23
PARTIAL_STREAM=YES
QUALIFICATION_COMPLETE=NO
MILESTONE_EXIT=0
MILESTONE_START=2026-09-04T12:01:28.5833984-03:00
MILESTONE_END=2026-09-04T20:02:35.1190396-03:00
MILESTONE_ELAPSED_SECONDS=28799.25363230001

MILESTONE_HEAD=1ec76af89992f119865a370488593ad5c85c4c49
CANDIDATE_SHA=82c9cd4a973eefccf4149231ca84b16174a287611a5aae72c26564b01cc88dfd
CANONICAL_SHA=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
CANONICAL_BYTES=225699
CANONICAL_MUTATION=NO

MILESTONE_COUNTS=F=23 B=457 D=46 V=1901 M=16 I=2374 O=1406 R=1866 C=633 A=682 T=463 Z=0
LAST_FUNCTION_INDEX=22
LAST_FUNCTION_NAME=emit_ir_return
F23_ELAPSED=28122.663310999982
F24_ELAPSED=UNAVAILABLE
DEVELOPMENT_FRONTIER_F=23
FULL_QUALIFICATION_FRONTIER_F=23
PREVIOUS_FRONTIER_CROSSED=NO
LAST_MILESTONE_RESULT=TARGET_NOT_REACHED

COMPILEALL=PASS
DIFF_CHECK=PASS
COMMIT=NO
PUSH=NO
STAGE2=NOT_STARTED
NEXT_SAFE_ACTION=diagnose the F24 frontier locally; do not run full qualification yet
```

## Checkpoint 2026-09-04 - SHARED MATCH TERMINAL RESULT FIX + LOCAL GATES

- Candidate: selfhost/compiler/stage1_semantic_event_spine.s3
- Candidate SHA256: $candidateHash
- Canonical SHA256: $canonicalHash
- Canonical protected identity preserved: YES
- F24 pre-milestone local gate: PASS
- Focused semantic event-spine tests: PASS (pytest exit 0)
- Workflow path coverage audit: selfhost/** and stdlib/** added to push and pull_request filters
- Marker registration and stabilization workflow tests: PASS
- Root cause fixed: all-direct-return match arms were incorrectly encoded as explicit successor kind 3; shared terminal constructor now emits kind 2 without special-casing canonical input
- Boundary canary: classify -> after preserved
- Canonical probe rerun after fix: NO
- Stage2 started: NO
- Commit/push: NO

Next authorized action: one bounded TARGET_F=24 milestone probe; no full canonical qualification.

## Checkpoint 2026-09-05 - NESTED TERMINAL RESULT UNPACK FIX

- Candidate: selfhost/compiler/stage1_semantic_event_spine.s3
- Candidate SHA256: 535b13811a7daa6a6c92f64dd5b39e9c841e471d398bb0b9d9561a5fc7757014
- Canonical SHA256: 44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
- Canonical protected identity preserved: YES
- Root cause: nested terminal match results were reused as raw next-value IDs and double-packed by the enclosing relation
- Correction: shared lowering_result_next_id decoder unwraps nested terminal results before outer terminal packing
- Call-condition coverage: terminal call-match dispatch now uses the existing call fallthrough handler and shared all-terminal predicate
- Boundary canary: PASS (nested all-terminal match advances to following function)
- Focused match/call/continuation regressions: PASS
- Compileall: PASS
- Diff check: PASS
- Canonical probe rerun after fix: NO
- Stage2 started: NO
- Commit/push: NO

Next authorized action: one bounded TARGET_F=24 milestone probe after this locally proven correction.

## Checkpoint 2026-09-05 - F24 ATTEMPT AFTER SHARED TERMINAL MATCH FIX

- Transcript: scratch/stage1-milestone-f24-after-terminal-match-fix-20260904.txt
- Candidate SHA256: eeddc241c168b586f0e72b36ad1fbb93261b6031a56e23b7e22f8b6a4e1cc583
- Canonical SHA256: 44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
- Target: F24
- F observed: 23
- Last function: index 22, mit_ir_return
- Counts: F=23 B=457 D=46 V=1901 M=16 I=2374 O=1406 R=1866 C=633 A=682 T=463 Z=0
- Probe exit: 0
- Partial stream: YES
- Milestone reached: NO
- Qualification complete: NO
- Canonical modified during attempt: NO
- New canonical probe authorized: NO; diagnose the remaining local semantic loss before any further milestone
- Stage2 started: NO
- Commit/push: NO

This is a terminal result for the single F24 attempt after the shared all-terminal-match result fix; do not rerun the same milestone without a new, locally proven correction.
