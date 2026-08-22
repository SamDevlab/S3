# ABL V2.2 Shadow Promotion Hardening

## Result

The bounded V2.2 campaign used source lock `04d94a5368106c1f476ac8856a1a313eedea7b37` and compared only `BASELINE`, `COMPACT_EA`, `SCALAR`, and `COMPACT_EA_SCALAR`. The default backend remained byte-identical and the modes remain internal, experimental, and opt-in.

Compact EA generalized across 91 corpus cases and 107 indexed candidates. The observed result was 91 applications, 91 avoided temporaries, 91 removed instructions, 91 removed moves, zero hard regressions, and 16 safety rejections. The desired 100-application target was not reached, so coverage is honestly classified as `INSUFFICIENT_FOR_TARGET`; no synthetic repetitions were added.

Scalar replacement produced 10 genuine candidates, 9 promotions, 9 neutral promotions, 1 safety rejection, zero new spills, and zero new reloads. The evidence remains `CONTINUE_SHADOW_RESEARCH`; scalar replacement did not enter canary mode.

The Shadow Governor evaluated 91 decisions: 37 non-baseline recommendations, 54 baseline fallbacks, zero harm, and a 1.000 non-dominated rate. The static/hosted evidence is retained as `SHADOW_GOVERNOR_RESEARCH_ONLY` because native correctness did not close.

## Native Correctness

One Linux x86-64 policy matrix was executed: 100 comparisons across 25 workloads and B/C/S/CS. It produced 96 passes and 4 failures, all the same `A07` workload under all four policies. The emulator returned `5`; the native binary returned `2` with exit code `0`. Inspection identified a pre-existing TMOV register-residence correctness defect, independent of the V2.2 policy choice. No individual failure rerun was performed.

Therefore `T3=FAIL_LINUX_X86_64_CORRECTNESS`, `COMPACT_EA_CANARY_ELIGIBLE=NO_T3_CORRECTNESS_FAILURE`, and the campaign recommendation is `STOP_PROMOTION_CORRECTNESS_OR_GENERALIZATION_BLOCKER`.

T0, T1, and T2 passed. P7/P8/P9 were not executed because the S3-Benchmarks repository and PR #12 remained read-only; they are `DEFERRED_BY_CONSTRAINT`, not PASS. T4 and the full S3 suite were not run. No timing was used for selection and no native speedup claim is made.

The offline dataset contains 80 deterministic records with 25 static features and is `DATASET_FORMING`; no ML model was trained. RC1/main/S3-Benchmarks and PR #12 were not mutated. PR #190 remains open, Draft, unmerged, and not Ready for Review.
