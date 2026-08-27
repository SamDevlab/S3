# Stage1 semantic lowering — Codex handoff

Date: 2026-08-27

## Provenance

- Repository: `SamDevlab/S3`
- Base PR: `#268`
- Base branch: `feature/actual-stage1-compiler-seed-20260824`
- Frozen base SHA: `0789ad2df5f200c6b35b67d591d10e016c1a557a`
- Parallel implementation branch: `parallel/pr268-semantic-lowering-v1-20260827`
- Parallel Draft PR: `#270`
- Canonical `selfhost/compiler/s3c_stage1.s3` mutated by this work: **NO**
- PR #268 mutated by this work: **NO**

The branch tip may advance after this document is written for metadata-only handoff commits. Codex must use the current head of PR #270, while preserving the frozen base provenance above.

## What this handoff completes

The semantic architecture that was missing from the Stage1 effort is now specified by executable code rather than prose only.

### Authoritative v2 artifacts

- `tools/stage1_semantic_stream_v2.py`
  - hosted typed semantic oracle;
  - resolves functions and blocks numerically;
  - links AST source bindings to IR function IDs by resolved function name;
  - separates logical value identity from physical storage;
  - resolves numeric JUMP and BRANCH3 targets;
  - emits deterministic S3IR2 v2.

- `selfhost/compiler/stage1_semantic_stream_v2.s3`
  - ordinary S3 emission primitives for every frozen v2 record;
  - bounded streaming design;
  - decimal emission is not limited to three digits;
  - standalone fixture always emits `Z 0`, never a false completeness claim.

- `tools/verify_stage1_semantic_conformance_v2.py`
  - strict hosted-vs-Stage1 semantic equivalence gate;
  - candidate value IDs may differ from hosted register IDs;
  - mapping is reconstructed from parameter order, exact source binding names and instruction result edges;
  - physical storage IDs are not treated as semantic identity;
  - validates instructions, O/R def-use edges, calls/A edges and terminator value/target edges.

- `reports/selfhost/stage1/semantic-ir-v2-handoff-contract.json`
  - machine-readable frozen contract.

- `tests/test_stage1_semantic_stream_v2.py`
  - five-lane oracle closure;
  - round-trip conformance;
  - semantic opcode mutation rejection;
  - incomplete-mask rejection;
  - numeric BRANCH3 target coverage.

### v1 artifacts

The v1 files remain useful as prototype/history only. They are not the handoff protocol.

In particular:

- `tools/patch_stage1_semantic_port_v1.py` is a candidate-only S1 prototype for parameter/local source identity;
- `tools/patch_stage1_semantic_probe_v1.py` and `tools/check_stage1_semantic_probe_v1.py` are probe scaffolding;
- `tools/stage1_semantic_stream_protocol.py` and `selfhost/compiler/stage1_semantic_stream_v1.s3` are superseded by v2 for new integration work.

Do not promote a v1 completeness result as v2 evidence.

## Frozen S3IR2 v2 protocol

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

`Z 31` is the only complete state.

Bits:

```text
1  = S1 typed values + source bindings
2  = S2 instruction def/use
4  = S3 call dataflow
8  = S4 complete terminators
16 = S5 canonical serialization
```

Any unresolved semantic condition must produce a mask lower than 31.

## Terminator convention

### RETURN

- `kind = 1`
- `return_value_id >= 0` when the return carries a value;
- all target fields are `-1`.

### JUMP

- `kind = 2`
- the sole destination is stored in `target_negative`;
- `target_zero = -1`;
- `target_positive = -1`.

### BRANCH3

- `kind = 3`
- exactly one `condition_value_id`;
- exactly three numeric targets in negative / zero / positive order.

## Identity and storage rules

These rules are non-negotiable for the integration:

1. semantic value ID is not a physical slot;
2. the legacy four 365-entry banks are not the semantic namespace;
3. do not permanently reserve `[0,64)` as the parameter semantic-ID domain;
4. logical IDs may increase while physical parser/lowering scratch is reused;
5. source binding identity is function + lexical scope + exact source identifier;
6. Stage1 v2 source anchors currently target the ASCII self-hosting subset, matching the canonical Stage1 source;
7. storage IDs may differ between hosted and self-hosted lowering without changing semantic identity;
8. an O/A/T edge may never reference an undefined logical value;
9. one logical instruction result may have exactly one R definition;
10. unresolved symbol/type/block/callee/terminator state is fail-closed.

## Target architecture for Codex

Use a two-pass Stage1 candidate.

### Pass 1 — symbol/signature/source-binding pass

Collect only what must survive across the module:

- function ID / exact name span / foreign-vs-internal;
- parameter order, type and exact name span;
- source-local binding identity needed for name resolution;
- function signature information needed to resolve calls.

Do not materialize the entire instruction/value graph in module-global arrays.

### Pass 2 — streaming semantic lowering

Re-scan the source and lower one function / block / expression at a time using bounded reusable scratch.

Required vertical order:

```text
literal / identifier / unary / binary / index / call
    -> typed logical value
    -> I record
    -> O edges
    -> R edges
    -> C/A when call
    -> T when control-flow terminator
    -> B close
```

Emit completed records as soon as their semantic dependencies are known.

## Codex implementation scope

The first Codex change should create a **new candidate transform or candidate source**, not edit `s3c_stage1.s3` in place.

Recommended new file:

```text
tools/patch_stage1_semantic_port_v2.py
```

It may reuse proven portions of the v1 S1 prototype, but its output contract must be S3IR2 v2.

Implement in this order:

1. exact function IDs/name spans and parameter bindings;
2. local/loop-variable lexical binding lookup;
3. integer/tryte/trit literals and identifier uses;
4. unary/binary expressions with precedence;
5. assignments and local initialization;
6. internal and foreign calls with ordered arguments/results;
7. indexing / fixed arrays needed by canonical Stage1;
8. RETURN;
9. JUMP generated by loops/control flow;
10. MATCH lowering to BRANCH3 with negative/zero/positive ordering;
11. canonical deterministic record ordering;
12. only then `Z 31`.

## Required local qualification commands

Run on Linux x86-64 from the repository root.

### 1. Hosted v2 oracle

```bash
python -m pytest -q tests/test_stage1_semantic_stream_v2.py
python -m bootstrap.s3.cli check selfhost/compiler/stage1_semantic_stream_v2.s3
```

Both must pass before changing Stage1 integration code.

### 2. Keep the canonical source unchanged while building the candidate

```bash
sha256sum selfhost/compiler/s3c_stage1.s3
```

Record this SHA before and after candidate qualification.

### 3. Generate candidate

Use the new v2 candidate transform, for example:

```bash
mkdir -p .artifacts
python tools/patch_stage1_semantic_port_v2.py \
  --output .artifacts/s3c_stage1_semantic_v2.s3
```

### 4. Stage0 check

```bash
python -m bootstrap.s3.cli check .artifacts/s3c_stage1_semantic_v2.s3
```

### 5. Native Stage0 -> Stage1 build

```bash
python tools/build_stage1_compiler.py \
  .artifacts/s3c-stage1-semantic-v2 \
  --source .artifacts/s3c_stage1_semantic_v2.s3
```

### 6. Native semantic fixtures

Run the candidate with focused source fixtures through stdin and capture its S3IR2 v2 stream. The candidate may use a semantic-probe mode, but that mode must be candidate-only and must never alter canonical behavior before promotion.

### 7. Strict conformance

For every captured stream:

```bash
python tools/verify_stage1_semantic_conformance_v2.py \
  fixture.s3 \
  fixture.s3ir2 \
  --output fixture.conformance.json
```

Required:

```text
STATUS=PASS
candidate_internal_status=PASS
Z=31
```

### 8. Canonical source self-input

After focused fixtures pass, feed `selfhost/compiler/s3c_stage1.s3` itself to the semantic candidate and require v2 conformance against the hosted oracle.

This is the decisive precondition for proposing integration into the canonical Stage1 source.

## Minimum fixture matrix

Do not rely on one happy-path program.

Required cases:

- literal return;
- return parameter 0, 1, 2, 5, 6+;
- negative and wide i64 literals;
- mutable and immutable locals;
- local-to-local assignment;
- nested arithmetic with precedence;
- comparison / `<=>`;
- zero-argument call;
- 1, 2, 6 and 7+ argument calls;
- nested calls;
- foreign call;
- fixed-array declaration and index load/store;
- while with back-edge;
- break / continue if present in the canonical subset;
- match with all three ternary arms;
- nested match/while;
- large function with enough instructions that bounded scratch reuse is exercised.

Each fixture must persist source, stream and conformance JSON when it fails.

## Promotion gate

Do not mutate the canonical Stage1 or authorize SELF_EMIT merely because the hosted oracle passes.

Promotion requires all of the following:

```text
HOSTED_V2_ORACLE=PASS
S3_V2_PRIMITIVES=PASS
FOCUSED_NATIVE_V2_CONFORMANCE=PASS
CANONICAL_SOURCE_NATIVE_V2_CONFORMANCE=PASS
DETERMINISTIC_REPEAT=PASS
CANONICAL_SOURCE_SHA_UNCHANGED_DURING_QUALIFICATION=PASS
```

Only after those gates may the semantic v2 implementation be proposed for `selfhost/compiler/s3c_stage1.s3`.

After that promotion, the next stages are still separate gates:

```text
GENERAL_EMITTER
SELF_EMIT
STAGE2
STAGE3
T4
```

## CI state at handoff

The repository GitHub Actions environment currently returns the Stage1 semantic jobs as failed without exposing any workflow steps/logs. The same failure shape was already present on the frozen PR #268 base.

Classification:

```text
CI_INFRA_UNRESOLVED
```

Do **not** classify the current v2 code as test-failing solely from those no-step Action runs.

The local Linux qualification commands above are mandatory evidence for Codex.

## Current claims

```text
SEMANTIC_REFERENCE_LAYER=COMPLETE
S3IR2_V2_PROTOCOL=FROZEN
STRICT_CONFORMANCE_GATE=IMPLEMENTED
S3_V2_EMISSION_PRIMITIVES=IMPLEMENTED
SOURCE_BINDING_TO_IR_OWNER_NORMALIZATION=IMPLEMENTED
CANONICAL_STAGE1_MUTATED=NO
PR268_MUTATED=NO
NATIVE_STAGE1_V2_EVIDENCE=NO
SELFHOST_STAGE1_V2_INTEGRATION=NOT_YET_PERFORMED
GENERAL_EMITTER_AUTHORIZED=NO
SELF_EMIT_AUTHORIZED=NO
STAGE2_AUTHORIZED=NO
STAGE3_AUTHORIZED=NO
T4_AUTHORIZED=NO
```

This is the intended boundary between the ChatGPT semantic-design work and the Codex implementation/integration phase.
