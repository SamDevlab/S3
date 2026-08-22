# PR191 TMOV Correctness Review

The final review reproduced the exact A07 divergence on the V2.2 source lock
and canonical main/RC1. The minimal case is a value copy followed by source
redefinition: the emulator returns `5`, while the buggy native backend returns
`2`. The root cause is confirmed TMOV alias invalidation: a destination was
forwarded to a mutable logical source register instead of receiving a value
version.

The narrow repair materializes every non-self TMOV by reading the source and
writing the destination. Self-move initialization checks and instruction
accounting remain unchanged. No unsafe TMOV alias state remains in the x86-64
emitter.

Coverage is complete through T26. The new F64 native case compares retained
`1.5` against redefined `2.5` and returns an observable tryte result; emulator
and native both return `1` with register allocation disabled and enabled.
Reference copying, initialization, physical residence, CFG shapes, and the
historical alias-chain cases pass.

T0 passed. T1 passed with 74/74 cases and T2 passed with 220/220 cases. The
targeted Linux x86-64 checks pass, including the exact minimal reproducer and
A07. The frozen V2.2 recheck passes 100/100 across 25 workloads and the four
historical policies. Structural comparison remains 24/25 unchanged; A07 adds
2 MOVs and 2 instructions, with zero unrelated changes.

The review source lock is `d10532c0f2e2db07f1d342bd6c3dcc3c782199ae`.
After that lock only review reports were added. GitHub reports no checks for
the Draft branch, so CI is classified as `NO_CHECKS_REPORTED`, not as PASS.

PR #190 remains open, Draft, unmerged, and untouched. The Compact EA canary
remains disabled. No timing, T4, full suite, merge, tag, release, reboot, or
shutdown was performed.

Decision: `PR191_TECHNICALLY_READY_FOR_HUMAN_REVIEW`.
Recommended next action: `PR191_READY_FOR_EXPLICIT_INTEGRATION_DECISION`.
