# S3 1.1 R4 — Minimization and Triage

Status: **complete on the dedicated R4/R5 branch; R5 in progress**.

## Provenance

```text
BASE_MAIN=11d8ce2e0c80e5d92fb779e8b39f446efdb25120
R4_IMPLEMENTATION_HEAD=774849b1303e3fb726c2c4972457bfa88ba3247d
R4_BRANCH=feat/s3-1.1-r4-r5-reliability-closure-20260916
R4_SOURCE_SEMANTICS_CHANGED=NO
V1_0_0_TAG_IMMUTABLE=YES
```

The implementation is additive Reliability Lab tooling. No compiler, runtime,
IR, Assembly, backend, or frozen R0-R3 schema was changed.

## Implemented contract

- `tools/reliability_minimizer_v2.py` performs deterministic contiguous-line
  and contiguous-byte reduction.
- The original source must reproduce the expected result before reduction.
- A candidate is accepted only when both `outcome` and
  `failure_signature` match exactly.
- Evaluations are bounded by the frozen `minimizer_max_evaluations=10000`
  policy. The best verified candidate is retained at a budget boundary.
- Replay minimization verifies source, metadata, and result hashes before
  writing a separate minimized output directory. The original replay bundle is
  left unchanged.
- `tools/reliability_triage_v2.py` groups failures by the frozen pair
  `(outcome, failure_signature)`, orders groups by
  `(outcome, failure_signature, first_case_index)`, and sorts case IDs.
- The canonical machine report and Markdown report are generated from the
  same deterministic model. Canonical JSON is UTF-8 with sorted keys, compact
  separators, and a final newline.

The additive machine-report schema is
`spec/reliability/triage.schema.json`.

## Validation

```text
R4_FOCUSED_TESTS=101 passed
R4_FULL_SUITE=EXIT_0_AT_100_PERCENT
R4_DIFF_CHECK=PASS
R4_COMPILEALL=PASS
```

The focused selection covered the frozen R0 contract, R1 runner, R2
generation, R3 differential/replay, campaign/worker behavior, the new
minimizer, the new triage report, and replay hash/path validation. The full
`python -m pytest -q` run completed with exit code `0`; its quiet output did
not emit a numerical pass/skip summary, so no unobserved count is asserted
here.

## R4 exit decision

```text
R4_REDUCER=PASS
R4_EXACT_FAILURE_SIGNATURE_PRESERVATION=PASS
R4_DETERMINISTIC_GROUPING=PASS
R4_MACHINE_REPORT=PASS
R4_MARKDOWN_REPORT=PASS
R4_SYNTHETIC_REDUCTION=PASS
R4_REPLAY_INTEGRATION=PASS
R4_UNCLASSIFIED_FAILURES=0
R4_COMPLETE=YES
R5=IN_PROGRESS
MERGE_REQUESTED=NO
RELEASE_REQUESTED=NO
```

R5 is a separate bounded maintenance candidate and still requires its own
Windows regression, exact-source Linux execution, campaign provenance, and
release decision. Historical `v1.0.0` certification remains a baseline and is
not presented as a fresh R5 campaign.
