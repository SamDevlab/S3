# x86-64 TMOV Correctness Repair

The exact A07 workload reproduced with emulator result `5` and native result
`2` on both canonical main/RC1 (`9b39c7070d7bfa23d709c2128eb0b0bbef164177`)
and the V2.2 source lock. The minimal reproducer is the same value-copy
scenario: `r0=5`, `TMOV r1,r0`, `r0=2`, then read `r1`. The canonical main bug
classification is therefore proven; it was not a PR #190-only regression, a
harness error, or a bad oracle.

The root cause was confirmed in the x86-64 emitter. Local TMOV forwarding stored
`destination -> source` and resolved later reads through the mutable source
register. The selected repair conservatively materializes every non-self TMOV.
Self-move initialization and instruction accounting remain unchanged. The
repair is independent of stack versus physical residence and does not require
a new SSA or MemorySSA design.

T0, T1 (`73 passed`), T2 (`220 passed`) and targeted Linux x86-64 T3 passed.
The exact A07 and minimal reproducer pass after repair. The frozen V2.2 native
matrix passed `100/100` across 25 non-static workloads and four policies in a
disposable combined checkout. In a focused structural comparison, 24/25 cases
were unchanged; only A07 gained two lines and two `mov` instructions.

No timing was run and no speedup claim is made. T4 and the full suite were not
run. Compact EA canary remains disabled, although this correctness blocker is
cleared for later review. PR #190 remains open, draft and untouched. The fix is
ready for review in the separate canonical-main branch; nothing was merged.
