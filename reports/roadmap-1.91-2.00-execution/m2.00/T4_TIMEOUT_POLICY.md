# M2.00 T4 Timeout Policy

## Applied policy

The runner uses explicit finite timeout classes:

```text
DEFAULT=60S
HEAVY_SELF_HOSTING=180S
HEAVY_RENDERER=300S
T4_PARALLELISM=1
PROCESS_MODEL=ONE_PYTEST_SUBPROCESS_PER_FILE
TIMEOUT_SEMANTICS=WHOLE_FILE_WALL_CLOCK
UNKNOWN_CLASS=FAIL_CLOSED
```

The timeout class and applied seconds are recorded for every selected file.
Timeout is never converted to PASS. No filename pattern, prior result, or
unlimited class is used.

## Post-reboot pre-T4 evidence

After reboot, `tests/test_external_jsmn_s3.py` passed 5/5 fresh processes and
the required 10-run margin sequence passed 10/10. The margin sequence had
median `31.575s`, nearest-rank p95 `38.640s`, maximum `38.640s`, and CV
`0.0935`. All 15 controls passed; no orphan was detected. The classification
was `PRE_REBOOT_HOST_STATE_CONTAMINATION`, with a healthy default 60-second
margin.

## Authorized final T4

Exactly one final T4 was run after those preconditions:

```text
T4_HEAD=a651e9b3551f218af1c27bb908e0692880afc4da
SELECTED=369
PASS=365
FAIL=0
TIMEOUT=4
UNCLASSIFIED_TIMEOUT=0
EXIT=1
STATUS=TIMEOUT
```

Every timeout was explicitly classified:

```text
tests/test_assembly_renderer_candidate_readiness.py|HEAVY_RENDERER|300
tests/test_compare_assembly_renderer.py|HEAVY_RENDERER|300
tests/test_m150_renderer_component.py|HEAVY_RENDERER|300
tests/test_s3_renderer_sign_text.py|HEAVY_RENDERER|300
```

The immutable raw transcript is
`T4-final-post-reboot-20260821-054208.txt`. No timeout was rerun or triaged
by a separate test invocation. The four timeouts remain raw timeout results,
not PASS results, so the release gate remains blocked despite zero functional
failures and zero unclassified timeout rows.

```text
T4_RUNS_THIS_PROMPT=1
BENCHMARK_RERUN=NO
MERGE=NO
AUTO_MERGE=NO
FORCE_PUSH=NO
TAG=NO
RELEASE=NO
M2.01_STARTED=NO
```
