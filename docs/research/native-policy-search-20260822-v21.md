# Native Policy Search V2.1

V2.1 extends the V2 native-policy laboratory with attribution, ablation, and
a conservative shadow-only selector. The experiment is structural: it does
not use timing, does not alter the default `X8664Backend()` policy, and does
not produce a native speedup claim.

The attribution corpus is partitioned into indexed memory, scalar replacement,
register pressure, localized pressure, constant rematerialization, loop live
ranges, calls/ABI, references/aliasing, mixed realistic functions, and negative
controls. Each category carries positive and negative cases. The frozen
holdout is evaluated only after attribution decisions are fixed.

The Shadow Governor consumes only `FunctionFeatureVector` values and an
explicit eligible policy set. It falls back to baseline for references,
address-taken values, calls, insufficient structural evidence, correctness
failure, or a hard structural regression. Its output is discarded after the
counterfactual comparison; it is not a compiler integration point.

Live-range splitting is evaluated through a deterministic benefit/cost gate.
The gate records predicted and observed structural deltas and never forces a
split when estimated cost is greater than or equal to estimated benefit.

The canonical command is:

```text
python -m tools.native_policy_search_v21 --output-dir reports/native-policy-search-20260822/v2.1-attribution --source-lock <V21_SOURCE_LOCK> --campaign-start-head <START_HEAD>
```

Linux native correctness is a separate no-timing focused gate. T4, the full
suite, benchmark timing, production promotion, and release publication remain
outside this campaign.
