# S3 Reliability Lab v2 — R0 Contract

Status: **frozen for S3 1.1 R0**.

Protocol family: `s3.reliability.v2`

This document defines the contract that R1-R5 implement. It does not implement
process execution, generation, differential comparison, minimization, or release
certification by itself.

## 1. Normative identities

```text
CASE_RESULT_SCHEMA=s3.reliability.case-result.v2
CAMPAIGN_REPORT_SCHEMA=s3.reliability.report.v2
REPLAY_SCHEMA=s3.reliability.replay.v2
WORKER_REQUEST_SCHEMA=s3.reliability.worker-request.v1
WORKER_RESPONSE_SCHEMA=s3.reliability.worker-response.v1
GENERATOR_PROTOCOL=s3.reliability.generator.v2
RESOURCE_POLICY=s3.reliability.resources.v1
```

A schema/version change is required when a backward-incompatible field,
classification, seed rule, or worker-protocol rule changes.

## 2. Canonical outcome taxonomy

Case outcomes are exactly:

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

Meaning:

- `PASS`: a valid case produced the required successful/equivalent result.
- `EXPECTED_REJECTION`: malformed/adversarial input was rejected through an
  expected compiler diagnostic/failure boundary.
- `UNEXPECTED_REJECTION`: a generator-declared valid case was rejected.
- `UNEXPECTED_ACCEPT`: input whose contract requires rejection was accepted.
- `MISCOMPILE`: two applicable semantic oracles disagree on observable result.
- `CRASH`: the child terminated abnormally or through an unhandled failure that
  is not an ordinary compiler diagnostic.
- `TIMEOUT`: the parent watchdog deadline expired and the process tree was
  terminated and reaped.
- `NONDETERMINISM`: repeated identical source/configuration produced different
  canonical outcomes.
- `RESOURCE_LIMIT`: an explicit frozen source/output/campaign/process bound was
  exceeded.
- `HARNESS_ERROR`: protocol, serialization, setup, capture, or infrastructure
  failure prevented a compiler result from being adjudicated.

`PASS` and `EXPECTED_REJECTION` are non-failure terminal outcomes. Every other
outcome requires a non-empty structured failure signature.

Infrastructure-wide unavailability is campaign metadata, not silently rewritten
to `PASS`.

## 3. Deterministic case identity

A case is identified by:

```text
campaign_id
case_index
case_seed
generator_version
case_kind
source_sha256
compiler_head
configuration
```

`case_id` is:

```text
sha256(
  UTF8(campaign_id) || NUL ||
  ASCII(case_index) || NUL ||
  ASCII(case_seed) || NUL ||
  UTF8(generator_version) || NUL ||
  UTF8(case_kind) || NUL ||
  ASCII(source_sha256)
)
```

represented as 64 lowercase hexadecimal characters.

No PID, timestamp, hostname, absolute path, filesystem enumeration order, or
wall-clock duration participates in canonical identity.

## 4. Seed derivation

`campaign_seed` and `case_seed` are unsigned 64-bit integers represented as JSON
integers in `[0, 2^64-1]`.

For case index `i`:

```text
seed_material =
    ASCII(campaign_seed) || NUL ||
    ASCII(i) || NUL ||
    UTF8(generator_version) || NUL ||
    UTF8(case_kind)

case_seed =
    unsigned_big_endian_u64(
        SHA256(seed_material)[0:8]
    )
```

The generator must not depend on Python's global random state, hash
randomization, process ID, current time, filesystem ordering, or locale.

A generator version must map `(case_seed, configuration)` to identical source
bytes on every supported host. If the PRNG/template algorithm changes, the
generator version changes.

## 5. Exact source bytes

Worker transport carries source as Base64 plus SHA-256. UTF-8 decoding happens
inside the worker only when required by the compiler API.

The parent verifies:

```text
sha256(base64_decode(source_b64)) == source_sha256
```

before launching an adjudicated compiler operation.

CRLF/LF differences are source-byte differences and therefore produce different
source hashes. The harness must not normalize source bytes implicitly.

## 6. Worker protocol

One executable case uses one fresh killable child-process boundary.

The parent sends exactly one JSON request on stdin. The child emits at most one
canonical JSON response on stdout. Diagnostic/compiler stdout and stderr are
captured as payload fields or separate bounded channels; they must not corrupt
the protocol record.

The request never contains an arbitrary shell command. Operations are
enumerated:

```text
CHECK
RUN_HOSTED
RUN_NATIVE
```

Optimization is enumerated:

```text
O0
O1
```

Backends are enumerated:

```text
hosted
linux-x86_64-native
```

The worker response reports a completed child operation only. A timeout or
process-tree kill is adjudicated by the parent because a dead child cannot be
trusted to report its own timeout.

## 7. Watchdog and kill semantics

The watchdog uses a monotonic parent-side deadline.

Default policy:

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

On timeout:

1. mark the deadline breach in parent state;
2. terminate the complete child process group/tree;
3. wait at most `KILL_GRACE_MS`;
4. hard-kill surviving descendants;
5. reap the child;
6. classify `TIMEOUT`;
7. persist the replay bundle before continuing.

A timeout is not inferred from elapsed time after an in-process call returns.

Output over the frozen stdout/stderr cap is `RESOURCE_LIMIT`; truncation may be
used for diagnostic display but never as the canonical captured bytes.

R1 may implement platform-specific process-tree mechanics, but those mechanics
must satisfy the same observable contract.

## 8. Failure signatures

Failure signatures are short structured ASCII strings. They must not include
absolute paths, PIDs, timestamps, full traceback text, or unconstrained raw
diagnostic messages.

Minimum families:

```text
unexpected-rejection:<phase>:<diagnostic-code-or-family>
unexpected-accept:<phase>
miscompile:<oracle-pair>:<lhs-sha256>:<rhs-sha256>
crash:<operation>:<exit-or-signal-family>
timeout:<operation>:<backend>:<optimization>:<budget-ms>
nondeterminism:<comparison-kind>:<first-sha256>:<second-sha256>
resource-limit:<limit-name>
harness-error:<protocol-stage>:<error-family>
```

The same underlying failure should produce the same signature when replayed
against the same compiler head and configuration.

## 9. Replay contract

Every non-PASS/non-EXPECTED_REJECTION result persists a replay bundle.

Required bundle entries:

```text
input.s3
metadata.json
```

`metadata.json` follows `s3.reliability.replay.v2` and records:

- exact `case_id`;
- exact source SHA-256 and byte count;
- compiler head;
- generator version and seed;
- case kind;
- operation/backend/optimization/configuration;
- timeout/resource policy;
- expected outcome and failure signature;
- relative artifact hashes.

Replay first verifies bundle hashes. It then executes the same case contract.
Replay success means the expected failure signature is reproduced; it does not
mean the compiler outcome became `PASS`.

Paths stored in the bundle are repository/bundle-relative. Absolute paths are
forbidden.

## 10. Canonical JSON

Canonical machine-readable documents use:

```text
UTF-8
sort_keys=true
separators=(",", ":")
ensure_ascii=false
final_newline=true
```

Canonical hashes are computed over bytes before the final newline unless a
specific artifact contract states otherwise.

Canonical documents exclude nondeterministic telemetry. Human-oriented reports
may add timing/host information only in explicitly noncanonical sections.

## 11. Campaign ordering

Cases are persisted in ascending `case_index`. Parallel execution, if introduced
later, must not change report ordering.

Failure groups are sorted by:

```text
(outcome, failure_signature, first_case_index)
```

Coverage keys are sorted lexicographically.

## 12. R0 acceptance boundary

R0 is complete when repository evidence proves:

```text
R0_SCHEMA_IDS_FROZEN=YES
R0_FAILURE_TAXONOMY_FROZEN=YES
R0_WORKER_PROTOCOL_FROZEN=YES
R0_WATCHDOG_CONTRACT_FROZEN=YES
R0_SEED_CONTRACT_FROZEN=YES
R0_RESOURCE_POLICY_FROZEN=YES
R0_FOCUSED_SCHEMA_TESTS=PASS
```

R0 does not claim:

```text
ISOLATED_RUNNER_IMPLEMENTED=NO
REAL_HANG_KILL_TESTED=NO
GENERATOR_V2_IMPLEMENTED=NO
DIFFERENTIAL_CAMPAIGN_RUN=NO
MINIMIZER_V2_IMPLEMENTED=NO
S3_1_1_RELEASE_AUTHORIZED=NO
```
