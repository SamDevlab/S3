# S3 1.1 R3 execution attempt 1

Date: 2026-09-15

## Execution identity

- execution SHA: `968982e63e9d7a373432ae27ec78c1ed3b02f9ef`
- platform: Ubuntu 26.04 LTS, Linux 7.0.0-31-generic, x86_64
- Python: 3.13.15
- compiler driver: GCC 15.2.0 via `/usr/bin/cc`
- GNU assembler: 2.46
- GNU ld: 2.46

## Preflight

- `git diff --check`: PASS
- `compileall`: PASS
- focused R0-R3 tests: `83 passed`, `0 failed`, `0 skipped`

## Campaign invocation

The one authorized campaign invocation was consumed before any generated case executed.

Requested campaign:

- id: `r3-linux-final-20260915`
- seed: `20260915`
- cases: `128`
- native cases: `16`

Observed result:

```text
R3_CAMPAIGN_EXIT_CODE=1
R3_CAMPAIGN_ERROR=ModuleNotFoundError: No module named 'tools'
R3_HOSTED_CASES=0
R3_NATIVE_SELECTED=0
R3=NOT_COMPLETE
READY_FOR_R4=NO
```

No `campaign.json` was created and no replay bundle was expected because the failure occurred before campaign execution.

## Root cause

`tools/reliability_campaign_v2.py` imported `tools.*` modules while being invoked as a file:

```text
python tools/reliability_campaign_v2.py ...
```

For direct script execution, Python places the `tools/` directory rather than the repository root at `sys.path[0]`. The top-level `tools` package therefore could not be resolved. The focused pytest suite imported the CLI as a module from the repository root and consequently did not exercise this entry-point condition.

This is a campaign harness/import-path defect. It is not evidence of an S3 compiler, optimizer, hosted runtime, or Linux x86-64 native backend failure.

## Raw evidence hashes

- stdout: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- stderr: `0b3f696d96559e08ab14273dbf0b25795390dd74e82fe5b0bc94c8812fbe99e3`
- status: `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`
- environment: `e0301457e676d77553ac3d6068d71aad2d3042bf3dcfb9fae21ba509049bf871`
- SHA256SUMS manifest: `678217b063b49da2ed61b9b9496c9ff0185fc199aab9fe307642a49407575e78`

Raw evidence root reported by the executor:

```text
/home/vboxuser/s3-r3-evidence-20260915-223617
```

## Repair boundary

The follow-up repair must remain limited to the R3 harness entry point/workflow and regression coverage. It must not change compiler/runtime/IR/backend/generator/differential semantics.

A new authoritative campaign requires a new explicit execution authorization against the repaired `main` SHA. Attempt 1 must not be rewritten as PASS or silently retried.
