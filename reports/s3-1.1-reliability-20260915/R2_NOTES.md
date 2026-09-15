# R2 notes

The generator intentionally cycles families by `case_index` before applying deterministic PRNG variation inside each family. This guarantees that a bounded initial cycle has explicit breadth instead of relying on random family selection.

Coverage is therefore measured by named feature/family counters rather than inferred from raw case count.

The generator version is frozen as `s3.reliability.generator.v2.0.0`; changing source bytes for an existing `(campaign_seed, case_index, case_kind)` requires a generator-version change or an explicit compatibility decision.
