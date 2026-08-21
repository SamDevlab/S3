# M1.91-M2.00 Terminal Correction Evidence

## Post-reboot JSMN gate

```text
JSMN_5X_PASS=5/5
JSMN_10X_PASS=10/10
JSMN_10X_MEDIAN=31.575
JSMN_10X_P95=38.640
JSMN_10X_MAX=38.640
JSMN_10X_CV=0.0935
JSMN_DEFAULT_60S_MARGIN=HEALTHY
CONTROL_PASS=15/15
ORPHAN_PROCESS_DETECTED=NO
```

## Authorized final T4

```text
T4_RUNS_THIS_PROMPT=1
FINAL_T4_HEAD=a651e9b3551f218af1c27bb908e0692880afc4da
SELECTED=369
PASS=365
FAIL=0
TIMEOUT=4
UNCLASSIFIED_TIMEOUT=0
EXIT=1
```

Timeout evidence is complete and explicit:

```text
tests/test_assembly_renderer_candidate_readiness.py|HEAVY_RENDERER|300
tests/test_compare_assembly_renderer.py|HEAVY_RENDERER|300
tests/test_m150_renderer_component.py|HEAVY_RENDERER|300
tests/test_s3_renderer_sign_text.py|HEAVY_RENDERER|300
```

The raw transcript is preserved as a new file. No source, runner, test,
benchmark, or historical transcript was modified during or after the T4.

```text
M2_00_T4=BLOCKED
BLOCKER=1
BENCHMARK_RERUN=NO
MERGE=NO
AUTO_MERGE=NO
FORCE_PUSH=NO
TAG=NO
RELEASE=NO
M2.01_STARTED=NO
```
