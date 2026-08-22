# ABL V2.1 Attribution and Shadow Governor

Status: STRUCTURAL_ATTRIBUTION_COMPLETE.

Attribution corpus: 60 cases; frozen holdout: 9 cases.

Genome identity: PASS. V2 global active genes: COMPACT_INDEXED_MEMORY, PRESSURE_AWARE_SCALAR_REPLACEMENT; V2 portfolio active genes: COMPACT_INDEXED_MEMORY, CONST_REMATERIALIZATION.

Attribution winner: V21_22e7512c33b0e8fd. Holdout winner, reported after evaluation and not used for tuning: V21_5155e2478b21c3b8.

Mechanism effects: compact EA POSITIVE with 52 structural applications and 52 avoided temporaries; scalar replacement POSITIVE with 1 promotion; region spill NEUTRAL despite 79 activations and 0 avoided spill/reload operations; rematerialization NEUTRAL; live-range split NEUTRAL with gate counts {'APPLY': 6, 'BORDERLINE': 42, 'SPLIT_REJECTED_BY_COST': 12}.

Shadow Governor: YES_RESEARCH_ONLY, harm count 0, non-dominated rate 1.000, overfit False.

Linux T3 correctness: PASS_LINUX_X86_64_FOCUSED, 96 comparisons across scalar, branch, call, indexed, mutable, mixed at O0, O1. No timing was used.

The strongest attributable structural result is compact indexed lowering, with a smaller conservative scalar replacement result. Region-aware spill, rematerialization, and live-range splitting do not yet show sufficient structural benefit to justify promotion. P7/P8/P9 remain deferred under the read-only benchmark constraint. T4 and the full suite were not run. The default backend and production policy remain unchanged; no native speedup claim or production candidate exists.
