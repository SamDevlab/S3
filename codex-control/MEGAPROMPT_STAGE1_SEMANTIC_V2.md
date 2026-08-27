# MEGAPROMPT — Codex Stage1 semantic lowering v2

You are continuing the actual self-hosting work in `SamDevlab/S3` around PR #268.

Your mission is not to repeatedly confirm the blocker. Your mission is to implement the missing semantic parser/lowering path required for a general Stage1 emitter, using the frozen S3IR2 v2 handoff as the semantic contract.

This prompt is controlled out-of-band by the branch:

```text
control/codex-stage1-semantic-v2-20260827
```

You MUST consult that branch throughout the work as described below.

---

## 0. CONTROL PLANE — MANDATORY BEFORE ANY DEVELOPMENT

Implementation branch:

```text
feature/actual-stage1-compiler-seed-20260824
```

Implementation PR:

```text
#268
```

Semantic handoff branch:

```text
parallel/pr268-semantic-lowering-v1-20260827
```

Semantic handoff PR:

```text
#270
```

Frozen semantic handoff HEAD used to initialize the control branch:

```text
c12e45d646af27f85b39c391d3a7645a812b28c5
```

Frozen historical PR #268 reference HEAD:

```text
0789ad2df5f200c6b35b67d591d10e016c1a557a
```

The LOCAL implementation worktree may have moved beyond those SHAs. Do not reset it back to a frozen SHA. Frozen SHAs are provenance/reference points, not instructions to discard later local work.

### Mandatory read-only control check

At startup, before every new numbered stage, before every implementation commit, before any change to canonical `selfhost/compiler/s3c_stage1.s3`, and before attempting SELF_EMIT/Stage2/Stage3/T4:

```bash
CONTROL_BRANCH=control/codex-stage1-semantic-v2-20260827
git fetch origin "$CONTROL_BRANCH"
CONTROL_REF="origin/$CONTROL_BRANCH"
git show "$CONTROL_REF:codex-control/CURRENT.json"
git show "$CONTROL_REF:codex-control/OVERRIDES.md"
```

Read the current stage file from the path in `CURRENT.json` when the revision has changed. If the revision has not changed and automatic advancement is allowed, proceed to the next numbered stage after completing the current one.

Remember the most recent `control_revision`.

Rules:

- NEVER checkout the control branch over the implementation worktree.
- NEVER merge the control branch.
- NEVER rebase onto the control branch.
- NEVER cherry-pick the control branch into PR #268.
- `git fetch` + `git show` are the intended access mechanism.
- If `control_revision` increases, re-read the selected stage and overrides before the next irreversible action.
- If `emergency_stop=true`, finish only the currently running atomic command, preserve evidence/worktree, then stop.
- If `pause_after_current_stage=true`, finish the current stage and its evidence, then stop.
- Authorization booleans in `CURRENT.json` are binding gates.

Every checkpoint must report:

```text
CONTROL_BRANCH=
CONTROL_REVISION=
CONTROL_ACTIVE_STAGE=
CONTROL_OVERRIDE_APPLIED=YES/NO
```

This allows ChatGPT/the user to change your route while you work without contaminating the code branch.

---

## 1. DO NOT FALL BACK INTO THE OLD LOOP

The following is NOT productive work and must not consume the run repeatedly:

```text
SSH_OK
Linux healthy
PR is OPEN/DRAFT/MERGEABLE
GENERAL_EMITTER_CAPABILITY_GAP
Stage2 not started
```

Do one initial infrastructure/status check. Repeat a specific infrastructure check only if a command actually fails for an infrastructure reason.

Statements such as:

```text
there is no later Stage1 parser/lowering implementation
five semantic lanes are missing
general emitter is blocked
Stage2 cannot start
```

are NOT stop conditions. They define the implementation backlog.

Do not spend the run merely adding another blocker paragraph to a report.

---

## 2. PRESERVE THE USER'S WORKTREE

At startup:

```bash
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
```

Record the result.

Do NOT:

- `git reset --hard`;
- clean untracked evidence/transcripts;
- discard local source modifications;
- rewrite history;
- force-push;
- merge PR #270;
- merge PR #268;
- run T4 early;
- create fake Stage2 artifacts.

If local edits exist in files you need, inspect them and build on them instead of replacing them blindly.

---

## 3. IMPORT/READ THE AUTHORITATIVE HANDOFF WITHOUT MERGING PR #270

Fetch the semantic branch:

```bash
git fetch origin parallel/pr268-semantic-lowering-v1-20260827
HANDOFF_REF=origin/parallel/pr268-semantic-lowering-v1-20260827
```

Read these authoritative v2 files from that ref:

```text
reports/selfhost/stage1/CODEX_HANDOFF_STAGE1_SEMANTIC_LOWERING_20260827.md
reports/selfhost/stage1/semantic-ir-v2-handoff-contract.json
tools/stage1_semantic_stream_v2.py
tools/verify_stage1_semantic_conformance_v2.py
selfhost/compiler/stage1_semantic_stream_v2.s3
tests/test_stage1_semantic_stream_v2.py
```

The v1 files in PR #270 are prototype/history only. They can be mined for proven parser hooks, but they do not define completeness.

If the authoritative v2 files are not yet present in the local implementation branch, selectively import/copy only the needed v2 contract/oracle/verifier/primitives/tests and handoff docs after checking for path conflicts. Do NOT merge the entire PR #270.

The semantic protocol is frozen unless a newer control revision explicitly authorizes a protocol revision.

---

## 4. FROZEN S3IR2 v2 CONTRACT

Header:

```text
S3IR2 2
```

Records:

```text
F function_id kind name_start name_length parameter_count result_count
B function_id block_id ordinal instruction_count terminator_instruction_id
V value_id function_id kind type_code anchor_start anchor_length mutable storage_id
M function_id storage_id type_code length mutable
I instruction_id function_id block_id ordinal opcode result_count operand_count aux_a aux_b
O instruction_id ordinal value_id
R instruction_id ordinal value_id
C instruction_id callee_kind callee_function_id callee_name_start callee_name_length argument_count result_count
A instruction_id ordinal value_id
T instruction_id kind condition_value_id target_negative target_zero target_positive return_value_id
Z completeness_mask
```

Completeness bits:

```text
1  = S1 typed values + source bindings
2  = S2 instruction def/use
4  = S3 call dataflow
8  = S4 complete terminators
16 = S5 canonical serialization
```

Only:

```text
Z 31
```

means complete.

Anything unresolved must fail closed with a lower mask or an explicit blocked/error result.

### Required semantic invariants

1. logical semantic value ID != physical storage slot;
2. legacy `4 x 365` value banks are NOT the semantic namespace;
3. no permanent semantic reservation of `[0,64)` for parameters;
4. scratch storage may be reused only when stale-reference safety is preserved;
5. completed semantic records should be streamed instead of retaining the entire canonical module graph in huge fixed arrays;
6. O/A/T edges may never reference undefined logical values;
7. an instruction result has exactly one R definition;
8. call arguments preserve source/semantic order;
9. calls preserve internal/foreign/builtin identity and result semantics;
10. RETURN carries a value ID when applicable;
11. JUMP has exactly one numeric block target;
12. BRANCH3 has exactly one condition value and exactly three numeric targets in negative/zero/positive order;
13. record ordering must be deterministic;
14. unresolved names/types/callees/blocks/results/terminators cannot be guessed;
15. physical storage IDs may differ from hosted Stage0 IR storage IDs without changing semantic identity.

---

## 5. TARGET COMPILER ARCHITECTURE

Implement a two-pass candidate.

### Pass 1 — symbols/signatures/source bindings

Collect only module information that truly must survive across functions:

- function IDs;
- exact function name spans;
- internal vs foreign;
- parameter count/order/types/name spans;
- return/result signature information;
- lexical binding metadata required for local/loop-variable name resolution;
- callable signature metadata needed for internal/foreign call resolution.

Do NOT materialize the entire instruction/value graph in global arrays.

### Pass 2 — streaming semantic lowering

Re-scan source one function/block/expression at a time.

Use bounded reusable scratch for:

- expression operator stack;
- expression value stack;
- local lexical binding table for the current function/scope;
- call argument staging;
- block/control stack;
- current instruction metadata.

Emit completed S3IR2 records once their dependencies are known.

Logical IDs can be module-monotonic or source-anchor-derived, but they must be deterministic and independent of physical scratch slots. If you change the ID policy, the conformance verifier must still reconstruct semantic equivalence; do not change the v2 record format.

---

## 6. DEVELOPMENT STRATEGY — CANDIDATE FIRST

Do not initially overwrite canonical:

```text
selfhost/compiler/s3c_stage1.s3
```

Create a new candidate transform, recommended:

```text
tools/patch_stage1_semantic_port_v2.py
```

The transform should generate:

```text
.artifacts/s3c_stage1_semantic_v2.s3
```

from the current canonical/local Stage1 source.

Every generated candidate must be deterministic for the same input source + transform HEAD.

Record:

```text
CANONICAL_SOURCE_SHA256
CANDIDATE_SOURCE_SHA256
CANDIDATE_SOURCE_BYTES
TRANSFORM_HEAD
```

Do not mutate canonical until the control plane explicitly authorizes it.

---

## 7. STAGE SEQUENCE

The detailed instructions live under `codex-control/stages/`. Check control before entering each stage.

### Stage 01 — precheck and import

Goal: preserve current local work, load control/handoff, establish exact provenance, and import only authoritative v2 support files if necessary.

No compiler semantics should be changed yet.

### Stage 02 — hosted contract qualification

Before writing the v2 candidate, prove the oracle/verifier/primitives locally:

```bash
python -m pytest -q tests/test_stage1_semantic_stream_v2.py
python -m bootstrap.s3.cli check selfhost/compiler/stage1_semantic_stream_v2.s3
python -m compileall -q \
  tools/stage1_semantic_stream_v2.py \
  tools/verify_stage1_semantic_conformance_v2.py
```

If this fails, diagnose and fix the contract implementation before touching Stage1 lowering.

Do not call an unavailable GitHub Actions runner a code failure without logs.

### Stage 03 — Pass 1: functions/signatures/bindings

Implement candidate-only function and binding tables.

Need real resolution for:

- internal functions;
- foreign functions;
- exact parameter ordinal/type/name;
- locals;
- loop variables;
- lexical scopes/shadowing;
- mutable/storage requirements.

At this stage S1 may remain PARTIAL because constants and instruction results are not yet lowered.

### Stage 04 — expression lowering: S1 + S2

Implement a real expression parser/lowerer, not lexical heuristics.

Minimum canonical subset:

- integer literals including negative/wide literals;
- trit/tryte/i64 typing;
- identifier use;
- unary operations;
- binary arithmetic/comparison with correct precedence;
- casts/conversions used by canonical Stage1;
- assignment/local initialization;
- load/store semantics as required;
- instruction result values;
- O and R edges.

Every use must resolve to a defined value.

Do not mark S1/S2 PASS until the conformance gate proves representative fixtures.

### Stage 05 — calls + arrays/indexing: S3

Implement:

- zero-arg calls;
- ordered N-arg calls;
- nested calls;
- internal call identity;
- foreign call identity/signature;
- call result values;
- A edges;
- fixed array/index load/store needed by canonical Stage1.

Use measured call-argument requirements; do not introduce huge speculative capacity.

### Stage 06 — control flow: S4

Implement semantic blocks and complete terminators:

- RETURN;
- JUMP;
- loop back-edges/exits;
- MATCH -> BRANCH3 negative/zero/positive;
- condition value IDs;
- numeric target block IDs;
- nested control constructs required by canonical Stage1.

No block may silently end without a terminator.

### Stage 07 — canonical deterministic serialization: S5

Make record ordering deterministic.

Require:

```text
F/B/V/M/I/O/R/C/A/T/Z
Z 31
```

only when S1-S4 are actually complete.

Run repeated candidate executions on the same fixture and require byte-identical stream output.

Run strict conformance for every focused fixture.

### Stage 08 — canonical-source-as-input qualification

Do NOT modify canonical compiler source yet.

Feed the canonical/current `s3c_stage1.s3` source as INPUT to the native candidate compiler and require strict S3IR2 v2 conformance.

This proves the candidate semantic front-end can represent the actual Stage1 program.

### Stage 09 — canonical integration

This stage requires:

```json
"canonical_stage1_mutation_authorized": true
```

in the current control manifest.

If false, stop after preserving Stage 08 evidence.

When authorized, integrate the already-qualified semantic path into canonical Stage1 with the smallest reviewable patch. Do not redesign while integrating.

### Stage 10 — General Emitter

After canonical semantic integration, re-run General Emitter qualification against the now-complete IR.

Implement emitter support from semantic records rather than source-specific shortcuts.

Do not proceed to self-emit because semantic lanes passed alone.

### Stage 11 — SELF_EMIT and bootstrap

Each action requires its corresponding control authorization.

SELF_EMIT -> Stage2 -> Stage3 -> T4 are separate gates.

Never generate fake artifacts to satisfy sequencing.

---

## 8. FOCUSED FIXTURE MATRIX

At minimum build/keep fixtures covering:

### Values/bindings

- literal return;
- wide positive literal;
- negative literal;
- parameter ordinals 0 through at least 6 when language ABI supports them;
- return first/third/sixth parameter;
- immutable local;
- mutable local;
- shadowed local in nested lexical scope;
- loop variable;
- assignment and reassignment.

### Expressions

- unary negative;
- `a + b`;
- precedence such as `a + b * c`;
- comparison;
- cast/conversion used by Stage1;
- nested expression results.

### Calls

- `f()`;
- `f(a)`;
- `f(a,b,...)`;
- nested `f(g(a))`;
- call result reused by another instruction;
- internal call;
- foreign call;
- call inside loop/control flow.

### Arrays/index

- fixed array local;
- index read;
- index write if canonical source requires it;
- index expression driven by a semantic value.

### Control

- direct return;
- while loop;
- loop exit/back-edge;
- match negative;
- match zero;
- match positive;
- nested branch/loop if canonical Stage1 uses it.

### Stress/capacity

- many arguments near measured requirements;
- many locals in one function;
- many instructions;
- many blocks;
- source above trivial size;
- repeated deterministic runs.

Persist failing fixture source + candidate stream + verifier JSON.

---

## 9. STRICT CONFORMANCE IS THE PROMOTION GATE

For every semantic fixture:

```bash
python tools/verify_stage1_semantic_conformance_v2.py \
  fixture.s3 \
  fixture.s3ir2 \
  --output fixture.conformance.json
```

Required:

```text
internal stream verification = PASS
semantic equivalence = PASS
completeness = Z 31
```

Candidate value IDs may differ from hosted IDs. The verifier should map by semantic structure/bindings/results, not physical slot number.

A passing parser that emits an incomplete mask is not a semantic PASS.

A deterministic wrong stream is not correctness PASS.

Hosted-only PASS is not native Stage1 PASS.

---

## 10. NATIVE LINUX QUALIFICATION

Use Linux x86-64 for native Stage1 evidence.

Generate candidate:

```bash
mkdir -p .artifacts
python tools/patch_stage1_semantic_port_v2.py \
  --output .artifacts/s3c_stage1_semantic_v2.s3
```

Stage0 check:

```bash
python -m bootstrap.s3.cli check .artifacts/s3c_stage1_semantic_v2.s3
```

Native Stage0 -> candidate Stage1 build:

```bash
python tools/build_stage1_compiler.py \
  .artifacts/s3c-stage1-semantic-v2 \
  --source .artifacts/s3c_stage1_semantic_v2.s3
```

Run focused fixtures through stdin, capture stdout as S3IR2 v2, stderr separately, and record exit code.

For each proof record:

```text
PLATFORM=
SOURCE_SHA256=
CANDIDATE_SHA256=
BINARY_SHA256=
FIXTURE_SHA256=
EXIT_CODE=
STDERR_MARKER=
STREAM_SHA256=
CONFORMANCE_STATUS=
```

Never claim native evidence from a hosted Python oracle.

---

## 11. CAPACITY AND MEMORY POLICY

Do not solve semantic identity by allocating gigantic fixed arrays.

The canonical source previously demonstrated that capacity tuning can become a distraction. Use measured bounds and streaming/reuse.

Allowed pattern:

```text
module-level function/signature table
+ bounded current-function binding scratch
+ bounded expression stack
+ bounded current-call argument staging
+ bounded control/block stack
+ streamed semantic records
```

Disallowed pattern without proof:

```text
semantic_value[50000]
instruction[50000]
operand_edge[100000]
```

If a bounded scratch capacity fails, measure the required peak, add justified headroom, record the measurement, and keep the failure fail-closed.

Logical IDs must continue to work even if scratch slots are reused.

---

## 12. COMMITS AND PUSHES

Before every commit, check the control branch again.

Commit only when an atomic slice has meaningful evidence.

Preferred shape:

```text
feat(selfhost): add Stage1 v2 lexical binding pass
feat(selfhost): lower typed Stage1 expressions to S3IR2 v2
feat(selfhost): add Stage1 v2 call dataflow
feat(selfhost): lower Stage1 control flow terminators
qualify(selfhost): prove native S3IR2 v2 conformance
```

Do not mix unrelated cleanup/formatting/research in semantic commits.

Do not merge PR #268 or #270.

Do not force-push.

If the implementation branch is expected to receive commits/pushes and local policy allows it, push only after tests/evidence for that slice. Preserve exact HEAD in the report.

---

## 13. TRUE STOP CONDITIONS

You may stop development early only for a real blocker such as:

1. required Linux/native infrastructure is unavailable and the next proof cannot be obtained anywhere else;
2. a concrete semantic contradiction exists between S3IR2 v2 and the actual language semantics;
3. continuing would require destroying or overwriting unreviewed user changes;
4. a proven physical/representation limit requires a redesign before any correct implementation can continue;
5. the control branch orders emergency stop/pause;
6. a required authorization gate is false.

These are NOT stop conditions:

- missing parser/lowering code;
- missing semantic lanes;
- General Emitter capability gap;
- Stage2 does not exist;
- a focused test fails because the feature has not been implemented yet;
- there is no later implementation to copy.

Those are development tasks.

---

## 14. DO NOT PROMOTE CLAIMS EARLY

Until proven:

```text
S1=BLOCKED/PARTIAL
S2=BLOCKED/PARTIAL
S3=BLOCKED/PARTIAL
S4=BLOCKED/PARTIAL
S5=BLOCKED/PARTIAL
GENERAL_EMITTER=BLOCKED
SELF_EMIT=NOT_AUTHORIZED or BLOCKED
STAGE2=NOT_STARTED
STAGE3=NOT_STARTED
T4=NOT_RUN
FULL_SELF_HOSTING=NO
```

Never infer `PASS` because code exists.

Never infer `PASS` because the host oracle passes.

Never infer `PASS` because a candidate compiles.

Never infer self-hosting because Stage1 can emit some assembly.

---

## 15. REQUIRED CHECKPOINT OUTPUT

After each numbered stage, produce a compact checkpoint like:

```text
CONTROL_BRANCH=control/codex-stage1-semantic-v2-20260827
CONTROL_REVISION=<observed>
CONTROL_ACTIVE_STAGE=<stage>
CONTROL_OVERRIDE_APPLIED=YES/NO

IMPLEMENTATION_BRANCH=
HEAD_BEFORE=
HEAD_AFTER=
WORKTREE_PRESERVED=YES/NO

HOSTED_V2_ORACLE=
S3_V2_PRIMITIVES=
CANDIDATE_STAGE0_CHECK=
NATIVE_BUILD=
FOCUSED_NATIVE_V2_CONFORMANCE=
CANONICAL_SOURCE_AS_INPUT_CONFORMANCE=
DETERMINISTIC_REPEAT=

S1_TYPED_VALUES=
S2_DEF_USE=
S3_CALL_DATAFLOW=
S4_TERMINATORS=
S5_SERIALIZATION=
GENERAL_EMITTER=
SELF_EMIT=
STAGE2=
STAGE3=
T4=

FIRST_REAL_BLOCKER=
NEXT_STAGE=
```

Do not replace evidence with narrative.

---

## 16. FINAL OBJECTIVE

The intended vertical path is:

```text
current S3 Stage1 source
        ↓
two-pass semantic parser/lowering candidate
        ↓
S3IR2 v2
        ↓
strict native conformance
        ↓
canonical source as input PASS
        ↓
controlled canonical integration
        ↓
General Emitter
        ↓
SELF_EMIT
        ↓
Stage2
        ↓
Stage3
        ↓
deterministic equivalence
        ↓
T4 / broader qualification
```

Your job is to advance this path, not merely describe why it is blocked.

Before entering each next box, consult the live control branch again. A newer revision may alter the route, pause it, add a fixture, change a priority, or authorize the next promotion gate.
