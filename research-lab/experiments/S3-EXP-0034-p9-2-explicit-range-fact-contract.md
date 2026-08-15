# S3-EXP-0034 - P9.2 Explicit Range-Fact Contract

```text
ID=S3-EXP-0034
STATUS=SUPPORTED_NEGATIVE
CAMPAIGN=P9_2_EXPLICIT_RANGE_FACT_CONTRACT_V1
TARGET_KIND=CORRECTNESS_CANDIDATE_NOT_MAIN
TARGET_SHA=045bbb1427af941b71d28b93cf1e5fe9bf245af7
RELATED_ZETTEL=S3-ZK-0059
```

## Question

Can a small, explicit and fail-closed contract preserve object identity, index
identity, static length, range, dominance and loop-carried validity facts from
validated Assembly to the native emitter for `TLOAD` and `TSTORE`?

The candidate was the correctness stack A+B, not `origin/main`. Correction A
introduced structural `InstructionSite` identity; Correction B made `TMOV` a
materialized value snapshot. Neither correction is counted as a P9 gain.

## Inputs And Controls

- historical P9 model on `5dd6844607ba3a2d5830ed836fb9026eed86d0fb`;
- the same model on candidate `045bbb1427af941b71d28b93cf1e5fe9bf245af7`;
- the adapted P9.1 obligation ledger over 15 workloads;
- fixed memory objects, scalar indexed operations and explicit CFG sites;
- reference, slice, call, escape, conversion, overflow, lifetime and malformed
  facts treated as unsupported or invalidating.

Every unsupported or invalidated fact retains its checked path. The 20
negative controls are recorded in `reconciliations/P9_2_RESULT.json`; each is
`CHECK_RETAINED`.

## Competing Models

### Model A - recompute at the native consumer

Recompute facts from validated Assembly and CFG. The bounded domain is
`ObjectIdentity x IndexIdentity x LengthIdentity x RangeStatus x ValidityStatus`.
At joins, facts intersect; disagreement becomes `UNKNOWN`. Definitions, calls,
aliases, escapes, conversions, overflow, stores and unsupported loop entries
kill the fact. `UNKNOWN` means the native check remains.

Model A was sufficient to classify the tested population, but it found no
path-complete dominating range proof. Result: all indexed checks retained.

### Model B - private verified fact

No private fact was needed. Structural `InstructionSite` is the appropriate
key if a future proof-bearing fact is found, but it cannot manufacture missing
object/index/length or failure-order evidence. Result: `NOT_NEEDED`.

### Model C - public Assembly contract

No evidence showed that a narrow public Assembly field was necessary after
Model A. Expanding the public format would add forgeable transport surface
without a demonstrated safe removable site. Result: `REJECTED_NOT_JUSTIFIED`.

## Result

The old P9 model reproduced exactly at `289500`. The A+B candidate measured
`289512`, a correctness-only structural delta of `+12`; this is not a P9
opportunity. The P9.1 ledger on the candidate reported:

```text
CLASSIFICATION_COVERAGE=1.0
REQUIRED_DYNAMIC=65224
AVOIDABLE_DYNAMIC=0
UNKNOWN_DYNAMIC=26456
PROVABLY_REDUNDANT_SITES=0
PROVABLY_REDUNDANT_DYNAMIC=0
CHECKED_FALLBACK_SITES=9060
```

The safety family remains material, but no safe avoidable subclass was found.
Therefore:

```text
SAFE_AVOIDABLE_SUBCLASS=NO
P9_2_SELECTION=NO_VALID_TARGET_YET
P9_PRODUCTION_STARTED=NO
```

The first fact-loss boundary remains
`ASSEMBLY_TO_EMITTER_RANGE_FACT_CONTRACT_NOT_EXPLICIT`. This is a research
observation, not authorization to add public proof plumbing.

## Promotion Gate

`PROTOTYPE=NOT_REQUIRED` because Model A found no candidate to prototype.
`NEGATIVE_CONTROLS=PASS`, `LAB_CONSISTENCY=PASS`, and native correctness for
the adapted candidate analysis passed. No production code, benchmark, GitHub
Actions run, PR or shutdown was performed.

## Next Smallest Experiment

Only if separately authorized, construct a tiny hand-written Assembly corpus
with a proof-bearing loop-carried object/index/length identity and an oracle for
all invalidators. The experiment must first demonstrate one sound removable
site before any broader data-flow or public-contract work is considered.
