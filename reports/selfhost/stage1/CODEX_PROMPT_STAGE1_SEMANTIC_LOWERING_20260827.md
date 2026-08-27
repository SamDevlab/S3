# Codex prompt — integrate Stage1 semantic lowering v2

Work in `SamDevlab/S3`.

Start by reading, in this order:

1. `reports/selfhost/stage1/CODEX_HANDOFF_STAGE1_SEMANTIC_LOWERING_20260827.md`
2. `reports/selfhost/stage1/semantic-ir-v2-handoff-contract.json`
3. `tools/stage1_semantic_stream_v2.py`
4. `tools/verify_stage1_semantic_conformance_v2.py`
5. `selfhost/compiler/stage1_semantic_stream_v2.s3`
6. `tests/test_stage1_semantic_stream_v2.py`

Provenance that must remain true:

- PR #268 base branch: `feature/actual-stage1-compiler-seed-20260824`
- frozen PR #268 head: `0789ad2df5f200c6b35b67d591d10e016c1a557a`
- ChatGPT parallel branch / Draft PR #270: `parallel/pr268-semantic-lowering-v1-20260827`
- do not rewrite history;
- do not merge PR #270;
- do not modify canonical `selfhost/compiler/s3c_stage1.s3` until candidate qualification is complete.

Mission:

Implement the actual two-pass semantic parser/lowering candidate for the current Stage1, targeting **S3IR2 v2** and the strict conformance verifier already present in the branch.

Do not redesign the semantic protocol. Treat S3IR2 v2 as frozen.

Architecture:

- Pass 1: functions/signatures/source bindings/call-resolution metadata.
- Pass 2: re-scan source and stream semantic lowering with bounded reusable scratch.
- Semantic logical IDs must not be physical storage slots.
- Never reinterpret the legacy four 365-entry banks as the semantic namespace.
- Do not reserve `[0,64)` permanently for parameter IDs.
- Fail closed on unresolved names, types, uses, callees, blocks, terminators or serialization.

Create a new candidate transform such as:

`tools/patch_stage1_semantic_port_v2.py`

Do not initially overwrite `selfhost/compiler/s3c_stage1.s3`.

Required implementation order:

1. function IDs and exact source name spans;
2. parameters and lexical local/loop bindings;
3. typed literals and identifier uses;
4. unary/binary expression lowering with precedence;
5. assignment/local initialization;
6. internal + foreign calls with ordered A edges and R results;
7. fixed array/index load/store required by canonical Stage1;
8. RETURN;
9. JUMP/back-edge for loops;
10. MATCH -> BRANCH3 negative/zero/positive;
11. deterministic F/B/V/M/I/O/R/C/A/T order;
12. `Z 31` only when all S1-S5 conditions are complete.

Use `selfhost/compiler/stage1_semantic_stream_v2.s3` for emission primitives. Do not replace it with a new format.

Before integration, run:

```bash
python -m pytest -q tests/test_stage1_semantic_stream_v2.py
python -m bootstrap.s3.cli check selfhost/compiler/stage1_semantic_stream_v2.s3
```

Generate a candidate under `.artifacts/`, then:

```bash
python -m bootstrap.s3.cli check .artifacts/s3c_stage1_semantic_v2.s3
python tools/build_stage1_compiler.py \
  .artifacts/s3c-stage1-semantic-v2 \
  --source .artifacts/s3c_stage1_semantic_v2.s3
```

For every semantic fixture, capture S3IR2 v2 and run:

```bash
python tools/verify_stage1_semantic_conformance_v2.py \
  fixture.s3 fixture.s3ir2 \
  --output fixture.conformance.json
```

Do not promote unless every representative fixture has `STATUS=PASS`, internal stream verification PASS and `Z 31`.

Then feed the canonical `selfhost/compiler/s3c_stage1.s3` itself to the native candidate and require the same strict v2 conformance.

Only after focused + canonical-source native conformance PASS may you propose a canonical Stage1 patch.

After canonical semantic integration, do **not** jump directly to Stage2. Re-run the General Emitter qualification. SELF_EMIT, Stage2, Stage3 and T4 remain separate gates.

Evidence discipline:

- report exact candidate source SHA256 and byte count;
- report exact binary/artifact SHA when available;
- preserve fixture source + stream + conformance JSON for failures;
- distinguish TEST_FAIL from environment/toolchain/CI failure;
- GitHub Actions currently has no-step failures on both this branch and the frozen base, so local Linux evidence is authoritative until that infrastructure issue is resolved;
- never claim native PASS without native execution output.

At completion, report:

```text
BRANCH=
HEAD=
CANONICAL_SOURCE_SHA_BEFORE=
CANONICAL_SOURCE_SHA_AFTER=
CANDIDATE_SOURCE_SHA=
HOSTED_V2_ORACLE=
S3_V2_PRIMITIVES=
FOCUSED_NATIVE_V2_CONFORMANCE=
CANONICAL_SOURCE_NATIVE_V2_CONFORMANCE=
DETERMINISTIC_REPEAT=
S1=
S2=
S3=
S4=
S5=
GENERAL_EMITTER=
SELF_EMIT=
STAGE2=
STAGE3=
T4=
```

If a gate is not proven, write `BLOCKED` or `NOT_RUN`; do not infer PASS.
