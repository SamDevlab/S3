# M2.40 Full-Lineage T4 Certification

## Candidate

- Candidate head: `a779776c55a38e2b31a9448f97ee7885729a75be`
- Tested source head: `e202bc9c13afc88169365376b041b4fa12dd8bf9`
- Source changed after final gates: `NO`
- Platform: Windows 10, Python `3.11.9`
- Profile: `full`
- Runner: `s3test.v1`
- T4 invocations: `1`
- T4 executions: `1`
- Additional T4 runs: `0`

## Result

The single authorized T4 completed terminally:

- Selected: `390`
- Passed: `390`
- Failed: `0`
- Timed out: `0`
- Unclassified timeouts: `0`
- Exit: `0`
- Skipped cases derived from pytest progress output: `82`
- Full-lineage T4: `PASS`

The runner assigns `DEFAULT`, `HEAVY_RENDERER`, and `HEAVY_SELF_HOSTING`
timeout classes to selected modules. No selected module timed out, so there is
no timeout list to report. The raw transcript is preserved unchanged at
`reports/certification/m240-rc-t4-20260822/t4-20260822-091108.raw.json` with
SHA-256
`7d05c1b1cf28088a6108e68f8a07c9a9d1aeeddd78e38e6161983f59d25da3b6`.

The persistent execution record is
`reports/certification/m240-rc-t4-20260822/t4-20260822-091108.status.txt`.

No benchmark, merge, tag, release, shutdown, reboot, or T4 retry followed the
execution.
