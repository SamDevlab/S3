# S3 M1.61-M1.70 Global T4 Plan

- Campaign base: `06324bccd0cfee03452d34c5f04596b8f3973813`
- Final implementation candidate: `8a5d018150401060a6b9b5ddfe91205d9bf21f1c`
- T4 head: `0bd50143d8e555b12d70849aef827761acfb8f34`
- Global impact: `YES`
- T4 required: `YES`
- Orchestrator/profile: `tools/s3test.py full`
- Selected: `338` discovered `tests/test_*.py` file nodes
- Per-file outer timeout: `60s`
- Fingerprint: `6100145909676ce46f016e063bece350cbfd3f045bf715ef0ad7c7008e0a8be4`

| File category | Selected | Reason | Subsystem | Milestone | Platform requirement | Timeout |
|---|---|---|---|---|---|---|
| `tests/test_*.py` discovered files | YES (338) | Full certification profile; global M1.61-M1.70 delta | Repository-wide integration; per-file result retained | M1.61-M1.70 plus transitive regression surface | Windows hosted execution; native Linux/Windows PE/WASI/trusted TLS are classified separately | 60s/file |

The selection is the sorted output of `discover_tests(root)` in the existing
orchestrator. The base-to-candidate impact plan selected the direct and
transitive affected tests; because the source delta is globally impactful, T4
uses the full profile to certify the complete deterministic test-file set.

The prior `.s3-test-state` was retained. Its pre-T4 T0/T3 records were not
treated as T4 evidence. The completed T4 record now has the fingerprint above,
and each node's raw output is available in `T4_STATE_SNAPSHOT.json` and
`.s3-test-state/latest.json`.
