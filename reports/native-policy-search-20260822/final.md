# Native policy search

Baseline: 9b39c7070d7bfa23d709c2128eb0b0bbef164177.

Total deterministic candidates: 31.
Correctness pass: 9.
Correctness disqualified: 22.
Baseline policy output identical: YES.
Pareto frontier: M0_R0_BASELINE, R1_CALLER_FIRST, R4_SHORT_CALLER_LONG_CALLEE, R9_CALL_AWARE_SELECTIVE_RESIDENCE, BEAM_R1_R9.
Best global policy: M0_R0_BASELINE.
Production candidate: NONE.
Production policy changed: NO.
Experiment branch: `experiment/native-policy-search-20260822`.
Final tested source HEAD: `5e5a70c2a810e0d52a6a03c9625022f9e108df9c`.
Source changed after final gates: NO.

Structural ranking used discovery cases only; holdout cases were evaluated after
the ranking inputs were fixed. The six synthetic holdout cases and three checked-in
Assembly regressions passed hosted/emission checks. P7/P8/P9 benchmark workloads
were not re-executed against this experimental HEAD, so holdout promotion is
INCOMPLETE_EXTERNAL_CORPUS.

The deterministic portfolio uses only generic static function features and its
leave-family-out selection remained stable. It is research-only and was not
integrated into production behavior. Its discovery ratios are memory
1.000000, stack
1.000000, instructions
1.000000, and frame
1.000000.

Unimplemented memory policies were disqualified before structural scoring.
No native timing was used for selection. NATIVE_SPEEDUP_CLAIM=NO.
T0/T1/T2 passed in the focused local gates. T3 passed in the Linux x86-64 VM:
the five final structural finalists were checked against the Emulator at O0/O1
over three small scalar/branch/call workloads, for 30 native comparisons.
T4 and the full suite were not run.
