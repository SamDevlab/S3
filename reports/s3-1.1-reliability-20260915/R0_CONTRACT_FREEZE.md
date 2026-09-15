# S3 1.1 R0 — Reliability contract freeze

Date: 2026-09-15

Base `main`: `00303316bcfdec619421b86151b72d2019ea1e82`

Branch: `feature/s3-1.1-r0-reliability-contract-20260915`

## Result

R0 freezes the protocol that R1-R5 must implement. No compiler/runtime/IR/backend
behavior is changed by this phase.

```text
R0_SCHEMA_IDS_FROZEN=YES
R0_FAILURE_TAXONOMY_FROZEN=YES
R0_WORKER_PROTOCOL_FROZEN=YES
R0_WATCHDOG_CONTRACT_FROZEN=YES
R0_SEED_CONTRACT_FROZEN=YES
R0_RESOURCE_POLICY_FROZEN=YES
```

## Frozen schema identities

```text
CASE_RESULT_SCHEMA=s3.reliability.case-result.v2
CAMPAIGN_REPORT_SCHEMA=s3.reliability.report.v2
REPLAY_SCHEMA=s3.reliability.replay.v2
WORKER_REQUEST_SCHEMA=s3.reliability.worker-request.v1
WORKER_RESPONSE_SCHEMA=s3.reliability.worker-response.v1
GENERATOR_PROTOCOL=s3.reliability.generator.v2
```

The v2 naming deliberately does not reuse the historical Reliability Lab
prototype's `s3.reliability.report.v1`.

## Failure taxonomy

```text
PASS
EXPECTED_REJECTION
UNEXPECTED_REJECTION
UNEXPECTED_ACCEPT
MISCOMPILE
CRASH
TIMEOUT
NONDETERMINISM
RESOURCE_LIMIT
HARNESS_ERROR
```

`PASS` and `EXPECTED_REJECTION` do not carry failure signatures. Every other
terminal case outcome requires a bounded structured signature.

## Watchdog correction versus historical prototype

Historical PR #238 checked elapsed time after an in-process compiler call
returned. That cannot terminate a genuinely hung compiler call.

R0 instead freezes a parent-side process watchdog:

```text
one executable case -> one fresh killable child
monotonic deadline
terminate process tree
250 ms grace
hard-kill survivors
reap child
persist TIMEOUT replay evidence
```

The worker protocol has no `TIMEOUT` response state because timeout adjudication
belongs to the parent.

## Frozen default resources

```text
HOSTED_CASE_WALL_MS=5000
NATIVE_CASE_WALL_MS=20000
KILL_GRACE_MS=250
STDOUT_MAX_BYTES=1048576
STDERR_MAX_BYTES=1048576
SOURCE_MAX_BYTES=32768
CAMPAIGN_MAX_CASES=10000
CAMPAIGN_WALL_MS=3600000
MAX_PARALLEL_CHILDREN=1
REPLAY_BUNDLE_MAX_BYTES=4194304
MINIMIZER_MAX_EVALUATIONS=10000
```

## Determinism contract

Case seeds are derived from SHA-256 over campaign seed, case index, generator
version and case kind. Exact source bytes are then SHA-256 identified. Worker
transport uses Base64 + SHA-256 and does not normalize CRLF/LF.

Canonical JSON uses sorted keys, compact separators, UTF-8, no ASCII escaping,
and a final newline. PIDs, timestamps, hostnames, absolute paths and wall-clock
durations are excluded from canonical identity.

Frozen vector:

```text
campaign_seed=42
case_index=7
generator_version=s3.reliability.generator.v2.0.0
case_kind=valid
case_seed=4153593214656228440

source_sha256=b9e35a6c7b3d7116ce6a8a1782f60d09e47c2f69ca18d0f85c01e7ba6d4890c5
case_id=dad28f906471f6a2a62ae331ed899b4ecc81ad47e73b4c03fe6f47632e4f3a46
```

## Focused validation

A contract-only isolated validation was executed against the new helper, schema
files and focused test module:

```text
21 passed
0 failed
```

This was not a full repository suite and is not presented as one.

GitHub Actions remains independently blocked by the already-tracked
runner-provisioning condition where jobs receive no runner and execute no steps.
That infrastructure state is tracked in issue #284 and is not reclassified as a
code-test failure here.

## R0 boundary

```text
ISOLATED_RUNNER_IMPLEMENTED=NO
REAL_HANG_KILL_TESTED=NO
GENERATOR_V2_IMPLEMENTED=NO
DIFFERENTIAL_CAMPAIGN_RUN=NO
MINIMIZER_V2_IMPLEMENTED=NO
FULL_REPO_TESTS=NOT_RUN
S3_1_1_RELEASE_AUTHORIZED=NO
```

## Next

R1 implements the worker process boundary from this contract and must prove a
real hanging child is terminated, hard-killed if necessary, reaped, and
classified without requiring a second uncontrolled process.
