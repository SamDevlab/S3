# Post-TMOV ABL Reconciliation

PR #190 remains open, Draft, and unmerged. The branch was reconciled with
canonical main using merge commit `66c507de323582efd42164082d3161c4a46f8a77`.
The source and test candidate is locked at
`934ad01b92ff263317233ccaeaf6de5204c16a07`; no source or test changes were
made after that lock.

The only merge conflict was in the x86-64 emitter. The canonical TMOV fix was
retained, the unsafe mutable alias state was not restored, and the ABL policy,
residence, Compact EA, scalar, and Governor mechanisms were preserved. The
historical V2, V2.1, and V2.2 locks and reports remain unchanged.

Correctness gates passed. The minimal TMOV reproducer and exact A07 pass in
both residence modes. The Linux x86-64 post-fix matrix passed `100/100` for
the four frozen policies over A07 and R01-R24. T0, T1, and T2 passed. Default
experimental-off output is byte-identical to canonical main on the
representative A07, memory, branch, and call corpus.

Fresh post-TMOV Compact EA evidence is 107 indexed candidates, 91 eligible,
91 applications, 16 safety rejections, 91 temporaries avoided, 91
instructions removed, 91 MOVs removed, and zero hard regressions. Coverage
remains `INSUFFICIENT_FOR_TARGET` at 91 cases; duplicate cases were not added.
Scalar remains shadow-only at 10 candidates, 9 promotions, zero positive, 9
neutral, zero negative, zero new spills, and zero new reloads. The Governor
has zero harm and zero policy-decision drift against the historical decision
set.

Compact EA is eligible for a later research-only canary gate, but the canary
is not enabled and no production policy changed. No timing, T4, full suite,
benchmark repository mutation, PR merge, tag, or release was performed.

Classification: `PR190_POST_TMOV_RECONCILIATION_COMPLETE`.
