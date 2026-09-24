# S3 PR Stack Graph

Snapshot time: 2026-09-24T15:03:09Z
Live head/state recheck: 2026-09-24T15:25:49Z
Repository: `SamDevlab/S3`
Current `main`: `4c7aaf4ad59fdacdd83f230e11a0bd979081c80a`

All PRs #301-#312 were live as OPEN, Draft, unmerged, and MERGEABLE at this
snapshot. Their current check rollups all report failures; this report records
the rollups but does not investigate or rerun CI.

## Edges

Declared PR bases:

```text
main -> #301 -> #302 -> #303 -> #304 -> #305 -> #306 -> #307 -> #308 -> #309
                                                                  ├-> #310
                                                                  ├-> #311
                                                                  └-> #312
```

Actual Git ancestry differs at the final fork. #309's source commit
`e07d0b5464bf472b2ca18993f3e196a234ff0fc5` is a child of #308; its two
documentation commits lead to #309 head `d064c17...`. PRs #310, #311, and
#312 fork from `e07d0b5...`, not from final #309 head `d064c17...`. Their
pairwise merge base is `1a76e341098b54a639fec22eecea362cc243c46f`. The
declared base is still #309. This is ancestry drift, not a source conflict;
the omitted #309 commits are documentation-only.

```text
#308 db0f6b1 -> #309 source e07d0b5 -> #309 docs 1d05a72 -> d064c17
                              ├-> P2 f4353c1 -> docs 28c8148 -> P2 fix 1a76e34
                              │                         ├-> #310 P2H -> b217808
                              │                         ├-> #311 readiness -> e28bdf1
                              │                         └-> #312 tests c07b2c4 -> 6a97b72
```

Edge kinds are recorded separately in `PR_STACK_GRAPH.json`: declared PR base,
actual Git ancestry, and observed functional dependency. A declared base or
shared ancestor alone is not treated as a functional dependency.

## Live Snapshot

| PR | Base SHA | Head SHA | Commits | Files (+/-) | Checks | Role |
| --- | --- | --- | ---: | ---: | --- | --- |
| #301 | `4c7aaf4` | `b82a94d` | 117 | 25 (+8917/-58) | 13 fail | Source frontend root |
| #302 | `b82a94d` | `469578b` | 2 | 3 (+559/-62) | 12 fail | Native identifier expressions |
| #303 | `469578b` | `6231eb6` | 2 | 3 (+574/-0) | 12 fail | Native statement sequences |
| #304 | `6231eb6` | `bf79e61` | 2 | 2 (+2367/-9) | 12 fail | Native program frontend |
| #305 | `bf79e61` | `48f2551` | 5 | 5 (+1413/-17) | 12 fail | Native i64 semantic execution |
| #306 | `48f2551` | `889ad59` | 5 | 5 (+1442/-8) | 12 fail | Typed native values |
| #307 | `889ad59` | `86dccea` | 4 | 3 (+432/-0) | 12 fail | Native indexed values |
| #308 | `86dccea` | `db0f6b1` | 4 | 17 (+775/-18) | 13 fail | Aggregate references |
| #309 | `db0f6b1` | `d064c17` | 3 | 7 (+244/-1) | 13 fail | Native RMSD kernel |
| #310 | `d064c17` | `b217808` | 8 | 9 (+1567/-37) | 13 fail | P2 plus rejected P2H |
| #311 | `d064c17` | `e28bdf1` | 9 | 12 (+2372/-37) | 13 fail | Readiness/governance review |
| #312 | `d064c17` | `6a97b72` | 5 | 13 (+1893/-37) | 13 fail | Semantic tests/evidence |

All current PR heads are OPEN/Draft/mergeable and have no merge commit. The
complete file lists and full base/head SHAs are in the JSON companion. Current
`main` is unchanged from #301's base: main-ahead 0, #309-ahead 144 commits,
merge base `4c7aaf4...`. Therefore current-main conflict classification is
`NONE`.

The live #312 files endpoint reports 13 changed files. Its list includes
`reports/s3-exact-segment-budget/SEGMENT_PLANNER_AUDIT.md`, omitted in the
earlier captured JSON list; the JSON inventory has been corrected. Live
head/state recheck found no PR movement. Mergeability values come from the
individual PR views in the original snapshot.

## Functional Dependency Finding

The self-host/scientific chain is a sequence of genuine capability steps, not
mere title ordering: #301 supplies the native source/token/syntax and
registration root; #302 extends its parser with source-derived identifiers;
#303 consumes that expression parser for ordered statements; #304 consumes
those statement structures for whole-program functions/calls/loops; #305
executes that program structure; #306 extends its semantic values to typed
i64/f64; #307 consumes the combined lexer/semantic/typed-value substrate to
construct and inspect indexed values; #308 consumes `NativeIndexedValue` and
adds call-bounded aggregate-reference semantics across the compiler/IR/runtime
layers; #309 consumes the borrowed f64-vector path and adds sqrt/RMSD.

P2 is different. Its exact code delta is confined to the x86-64 backend and
planner and was cherry-picked unchanged onto current `main` with no conflict.
The source files compile there. That proves no #301-#309 implementation symbol
is required by the P2 code. It does not transfer P2's `e07`-based output or
performance qualification to the older main baseline: the focused extraction
trial fails its frozen e07 assembly-byte assertion, and Linux native execution
was unavailable on this Windows host. The selected performance evidence also
includes RMSD, whose aggregate-reference/sqrt workload is supplied by #308/#309.

No branch was rebased, retargeted, pushed, merged, or closed. No test beyond
the one focused extraction run, no full suite, no benchmark, and no power
action was started.
