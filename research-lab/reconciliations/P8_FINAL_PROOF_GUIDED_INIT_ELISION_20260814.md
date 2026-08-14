# P8 final proof-guided native initialization-check elision

## Reconciliation

P8.4 began as a research comparison of bounded proof transport and native
recomputation. The exact production candidate was then implemented from fresh
`origin/main`, validated locally, published as PR #178, and merged without
enabling GitHub Actions.

```text
P8_NAME=P8_PROOF_GUIDED_NATIVE_INIT_CHECK_ELISION
P8_BASE=631b51e70562a33183ac14d0be5bbe2ddd140779
P8_IMPLEMENTATION_HEAD=87eb49cd19a78570f07d66ce7982650c8b422210
P8_PR=178
P8_MERGE=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
ORIGIN_MAIN_FINAL=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
P8_IMPLEMENTATION_ANCESTRY=YES
P8_MERGE_ANCESTRY=YES
P8_SELECTION=READY_FOR_IMPLEMENTATION
P8_STATUS=COMPLETE_MERGED
P9_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
REBOOT_EXECUTED=NO
```

## Technical result

The x86-64 backend recomputes a bounded definite-initialization predicate from
existing validated Assembly structure. It elides only exact native
`cmp`/`je` initialization checks. The public Assembly and verifier contracts
are unchanged. Unknown and potentially observable cases keep the checked path.

P8.3's 416 safe static sites and 1660 dynamic events were reproduced exactly.
The native consumer observed 402 sites and 1558 events. Across 12 workloads at
O0/O1, all 24 native pairs preserved semantics. Aggregate checks changed from
550 to 148, static instructions from 20903 to 20099, branches from 4746 to
4344, and text bytes from 107709 to 102646. Loads/stores remained 10175.

## Gate result

The complete Linux suite ran once on the exact candidate head and exited 0.
The first SSH-attached attempt is retained as an external harness interruption,
not product evidence; the persistent rerun is the authoritative result. The
post-merge focused smoke passed on `origin/main`. Actions permissions were
verified disabled and no run existed for the candidate branch.

Runtime and compile-time numbers were not measured under a directly comparable
protocol and are intentionally unavailable. No P9 implementation or reboot was
started.

## Durable artifacts

- `experiments/S3-EXP-0031-p8-final-proof-guided-init-elision.md`
- `zettelkasten/notes/S3-ZK-0056.md`
- external final report: `production-reports/p8-final-proof-guided-init-elision-20260813/`
