# T4 Failure Triage

## Historical Runs

The previously recorded T4 transcripts remain byte-for-byte unchanged. They
cover the earlier candidates and are not reused as evidence for the corrected
source.

## Authoritative Post-Review Run

```text
HEAD=7b99ebb9ae4119ecc54b96f78313f0996c476b09
COMMAND=python tools/s3test.py full --format json --timeout 60
START=2026-08-20T18:21:30.3782101-03:00
END=2026-08-20T19:01:21.8076525-03:00
SELECTED_FILES=369
PASS_FILES=342
FAIL_FILES=1
TIMEOUT_FILES=26
EXIT=1
RERUN=NO
```

## Failure Classification

The reproducible failure is:

```text
tests/test_m194_tls_server.py::test_tls_handshake_timeout_releases_reserved_budget
expected=PollKind.FAILED
observed=PollKind.PENDING
configuration=max_timeout_seconds=0.001
focused_triage=FAIL
```

The failure is outside the M1.99 self-move correction surface and remains an
open M1.94/T4 blocker. It was not converted to a skip and no source change was
made after the T4.

The 26 timeout files are recorded as Windows per-file orchestrator timeouts.
They are not promoted to PASS and were not individually rerun after T4.

```text
T4_TRIAGE_PASS_IN_ISOLATION=NO
T4_TRIAGE_PREEXISTING_TIMEOUT=UNVERIFIED
T4_TRIAGE_ENVIRONMENT_DEFERRED=26_ORCHESTRATOR_TIMEOUTS
T4_TRIAGE_REPRODUCIBLE_FAILURE=1
T4_TRIAGE_UNRESOLVED=1
```
