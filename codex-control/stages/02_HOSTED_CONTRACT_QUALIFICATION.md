# Stage 02 — Hosted S3IR2 v2 contract qualification

## Goal

Prove the semantic oracle, verifier, S3 emission primitives, and focused v2 regression tests before modifying the Stage1 semantic path.

## Required commands

```bash
python -m compileall -q \
  tools/stage1_semantic_stream_v2.py \
  tools/verify_stage1_semantic_conformance_v2.py \
  tests/test_stage1_semantic_stream_v2.py

python -m pytest -q tests/test_stage1_semantic_stream_v2.py
python -m bootstrap.s3.cli check selfhost/compiler/stage1_semantic_stream_v2.s3
python -m json.tool reports/selfhost/stage1/semantic-ir-v2-handoff-contract.json >/dev/null
```

## Interpretation

- Hosted PASS proves the contract implementation only.
- It is not native Stage1 evidence.
- GitHub Actions no-step failure is `CI_INFRA_UNRESOLVED` unless actual logs prove a code failure.

## If a test fails

Fix the handoff implementation on the implementation branch only if the local imported v2 file is demonstrably wrong. Preserve the frozen protocol; do not redesign record semantics to make a test pass.

## Exit gate

```text
HOSTED_V2_ORACLE=PASS
S3_V2_PRIMITIVES=PASS
V2_CONTRACT_JSON=PASS
```

Then re-check the live control branch before Stage 03.
