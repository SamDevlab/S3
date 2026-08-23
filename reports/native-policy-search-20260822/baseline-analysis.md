# RC1 native backend baseline analysis

Baseline SHA: `9b39c7070d7bfa23d709c2128eb0b0bbef164177`.

The explicit baseline policy preserves caller-first allocation for values not crossing calls and callee-first allocation for call-crossing values. Address-taken referents remain canonical stack values. The baseline output was byte-identical before candidate scoring.

Unsupported indexed-memory, scalar-promotion, forwarding, and region-island strategies were rejected before structural scoring. No source-specific or benchmark-specific production rule was introduced.

The benchmark checkout was inspected read-only. PR #12 was not merged and P7/P8/P9 workloads were not re-executed against this experimental HEAD; the holdout result is therefore explicitly incomplete for promotion.
