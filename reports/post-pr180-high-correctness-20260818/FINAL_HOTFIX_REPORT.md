# S3 Post-PR180 High-Correctness Repair

## Provenance

- `HOTFIX_BASE_SHA=76030c5d5428e47f6839c219c4930db4cb1862d8`
- `PACKAGE_FIX_SHA=cf5f8f925853ebbba34866296816d9f254b549e8`
- `THREAD_FIX_SHA=1223fd435fa724b01eb19123cbdd079589350895`
- `FINAL_CODE_TESTED_SHA=1223fd435fa724b01eb19123cbdd079589350895`
- `FINAL_EVIDENCE_HEAD=PENDING_REPORT_COMMIT`

## Closure

Both baseline defects were reproduced on the merged PR #180 line and repaired
with the smallest subsystem-local changes. The package resolver is now
reachable-graph scoped and fail-closed for conflicting identities. Thread
capacity admission is now atomic, ownership-preserving on rejection, and
slot-safe on failure and completion.

Gates passed: T0 sanity, T1 package, T1 threads, T2 M1.56, and T2 M1.69.
The impact map did not select M1.70 or T3. No tests were weakened. No M1.70
synchronization semantics were changed.

No full T4, full pytest, benchmark, CI rerun, push, PR creation, merge, tag,
release, branch deletion, Actions change, or shutdown was performed.

`POST150_RUNTIME_FIX_PRESERVED=YES`
`INSTRUCTION_LIMIT=100000`
`GC_INTRODUCED=NO`
`RAW_POINTERS_INTRODUCED=NO`
`ASYNC_INTRODUCED=NO`
`JIT_INTRODUCED=NO`
`UNEXPECTED_PRODUCTION_FILES=0`
`UNRESOLVED_CORRECTNESS_REGRESSIONS=0`
