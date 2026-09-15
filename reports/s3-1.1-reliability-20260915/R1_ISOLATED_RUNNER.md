# S3 1.1 R1 — Isolated runner

Date: 2026-09-15

Base: R0 merged on `main` at `89d52b9fa6302fd7711a7b07f60273d9284ca9ad`.

Branch: `feature/s3-1.1-r1-isolated-runner-20260915`

## Result

R1 implements the process boundary frozen by R0:

```text
ONE_FRESH_CHILD_PER_CASE=YES
PARENT_SIDE_MONOTONIC_WATCHDOG=YES
PROCESS_TREE_TERMINATION=YES
KILL_GRACE_MS=250
HARD_KILL_FALLBACK=YES
DIRECT_CHILD_REAP=YES
BOUNDED_PROTOCOL_CAPTURE=YES
COMPILER_REJECTION_DISTINCT_FROM_HARNESS_ERROR=YES
UNEXPECTED_WORKER_EXCEPTION_CLASSIFIES_CRASH=YES
RUN_NATIVE=FAIL_CLOSED_UNTIL_R3
```

No compiler/runtime/IR/backend behavior is changed by R1.

## Worker

`tools/reliability_worker_v2.py` is a single-request worker:

- reads exactly one bounded JSON request from stdin;
- verifies exact source bytes through Base64 + SHA-256 + byte count;
- decodes S3 source as strict UTF-8;
- supports `CHECK` and `RUN_HOSTED` in R1;
- catches typed `S3Error` only as ordinary compiler rejection;
- converts typed compiler diagnostics to stable code/family fields;
- intentionally allows unexpected Python/compiler exceptions to escape so the
  parent observes a non-zero worker exit and classifies `CRASH`;
- captures compiler stdout/stderr behind the frozen one-MiB per-channel bounds;
- emits one canonical JSON response;
- rejects `RUN_NATIVE` fail-closed until the R3 native differential phase.

## Parent watchdog

`tools/reliability_runner_v2.py` starts one fresh worker process per case.

POSIX process isolation uses a new session/process group. On timeout the parent
sends SIGTERM to the process group, waits the frozen 250 ms grace interval, then
sends SIGKILL to surviving descendants and reaps the direct child.

Windows uses a new process group and `taskkill /PID <pid> /T`, followed by
`/F` hard-kill fallback and direct `kill()` fallback if required. The same
observable timeout contract is preserved; platform mechanics are intentionally
not exposed in the case protocol.

The parent concurrently drains worker stdout/stderr so a flooding child cannot
deadlock the watchdog. Protocol-channel overflow is classified as
`RESOURCE_LIMIT` and triggers process-tree termination.

## Parent result boundary

The parent runner has infrastructure statuses:

```text
RESPONSE
TIMEOUT
RESOURCE_LIMIT
CRASH
HARNESS_ERROR
```

`RESPONSE` means the worker emitted a valid canonical protocol response. It does
not by itself mean the S3 case is a reliability `PASS`; later adjudication uses
case expectations and differential oracles.

This distinction prevents an ordinary compiler diagnostic (`REJECTED`) from
being conflated with a harness failure.

## Focused execution evidence available in this ChatGPT runtime

The private repository is not mounted in the execution container and GitHub
Actions is still not assigning runners, so the full repository test module
cannot be executed here against the real S3 package.

Two standalone, dependency-isolated probes were executed using the exact R0
contract semantics and the R1 process-boundary implementation:

```text
R1_PARENT_BOUNDARY_PROBES=8 passed
R1_WORKER_PROTOCOL_STUB_PROBES=5 passed
R1_FOCUSED_TOTAL=13 passed
R1_FOCUSED_FAILED=0
```

The parent-boundary probes included:

- canonical response acceptance;
- bounded channel transport;
- non-zero child exit -> `CRASH`;
- malformed protocol -> `HARNESS_ERROR`;
- a genuinely sleeping/hung child -> `TIMEOUT`;
- a hung child that spawned a descendant -> whole tree terminated before the
  descendant could create its marker file;
- protocol-output flood -> `RESOURCE_LIMIT` + reap;
- structured worker error distinct from crash.

The worker-protocol probes used a stub compiler boundary to exercise:

- completed hosted result;
- typed compiler rejection;
- unexpected exception -> non-zero worker crash;
- compiler stdout cap -> resource limit;
- native operation fail-closed during R1.

## Repository regression coverage

`tests/test_reliability_runner_v2.py` additionally contains integration tests
that run the real `tools.reliability_worker_v2` against the repository compiler
for:

- a valid hosted S3 program;
- a malformed S3 program producing `S3E_PARSE_SYNTAX`;
- native fail-closed behavior before R3.

These real-repository integration cases are checked in but are **not claimed
executed in this runtime**. They must run when a repository-capable local/CI
runner is available.

## Environment boundary

```text
LINUX_PROCESS_TREE_PROBE=PASS
WINDOWS_PROCESS_TREE_CODE=IMPLEMENTED_NOT_EXECUTED_HERE
REAL_REPOSITORY_WORKER_TESTS=CHECKED_IN_NOT_EXECUTED_HERE
GITHUB_ACTIONS=BLOCKED_RUNNER_PROVISIONING
```

The Windows implementation is not silently promoted to an executed PASS. A
later Windows hosted campaign must exercise it before any cross-platform
watchdog claim is made.

## R1 closure

Implementation closure for the track is:

```text
R1_ISOLATED_PROCESS_BOUNDARY=IMPLEMENTED
R1_REAL_HANG_KILL=PASS_LINUX_LOCAL_PROBE
R1_PROCESS_TREE_KILL=PASS_LINUX_LOCAL_PROBE
R1_DETERMINISTIC_PROTOCOL_CAPTURE=PASS_FOCUSED
R1_FAILURE_BOUNDARY=PASS_FOCUSED
R1_WINDOWS_RUNTIME_EVIDENCE=DEFERRED_ENVIRONMENT
R1_REAL_S3_INTEGRATION_EVIDENCE=DEFERRED_RUNNER_UNAVAILABLE
```

R2 may proceed because its deterministic generation work depends on the frozen
protocol and the isolated runner architecture, not on broad platform promotion.
R3 must obtain fresh real Windows hosted and Linux x86-64 execution evidence
before differential closure.

## Next

Start R2 from current `main` after R1 integration. Implement generator v2 as a
new deterministic grammar-aware generator and malformed/mutation pipeline; do
not import PR #238 wholesale.
