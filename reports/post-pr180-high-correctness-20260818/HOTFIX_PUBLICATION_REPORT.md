# Post-PR180 Hotfix Publication Record

This record covers publication of the locally verified corrective branch. It
does not authorize or perform a merge.

## Provenance

- `ORIGIN_MAIN_BEFORE=76030c5d5428e47f6839c219c4930db4cb1862d8`
- `HOTFIX_BASE_SHA=76030c5d5428e47f6839c219c4930db4cb1862d8`
- `PACKAGE_FIX_SHA=cf5f8f925853ebbba34866296816d9f254b549e8`
- `THREAD_FIX_SHA=1223fd435fa724b01eb19123cbdd079589350895`
- `FINAL_CODE_TESTED_SHA=1223fd435fa724b01eb19123cbdd079589350895`
- `REPORTED_EVIDENCE_SHA=82b1b98e5096945a9fcc3eb1f11aec0d5ba89f9e`
- `LOCAL_HEAD_BEFORE_PUBLICATION=808458882e2ecb02f89422d4d6d0a57ba755333a`

The changes after the code-tested SHA are reports only. The package and
thread fixes remain the only production changes, and the M1.70 executable
surface is unchanged.

## Publication gates

- origin/main moved since hotfix base: NO
- focused local gates: PASS
- unexpected production files: 0
- secrets/artifacts/machine-path audit: PASS
- git diff --check: PASS
- working tree: CLEAN
- CI: NOT_RUN_REPOSITORY_ACTIONS_DISABLED
- full T4, full pytest, and benchmarks: NOT RUN

The intended remote mutation is one normal push of
`fix/post180-high-correctness-20260818`, followed by one corrective PR against
`main`. No merge, auto-merge, direct main push, branch deletion, tag, release,
or shutdown is authorized.
