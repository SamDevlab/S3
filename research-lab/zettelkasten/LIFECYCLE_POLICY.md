# S3 Zettelkasten — Note Lifecycle Policy

```text
STATUS=ACTIVE
DATE=2026-08-15
CANONICAL_NOTE_LOCATION=research-lab/zettelkasten/notes/
PHYSICAL_NOTE_MOVE=NO
```

The Zettelkasten now separates notes by **epistemic lifecycle**, without moving the canonical `S3-ZK-*` files and without breaking historical wiki links, reconciliations or commit provenance.

## Two lifecycle classes

### PERMANENT

A permanent note records durable research knowledge.

It may be:

- a general principle supported by evidence;
- a correctness invariant;
- a scoped empirical result;
- a scoped negative result;
- a supported research model or research requirement whose scope is explicit;
- a historical result that remains true for the declared corpus/SHA/window.

`PERMANENT` does **not** mean globally universal.

A permanent note must state its scope when the evidence is bounded.

Examples:

```text
SUPPORTED
SUPPORTED_FOR_CORPUS
SUPPORTED_FOR_EXACT_CORPUS
SUPPORTED_AS_RESEARCH_MODEL
SUPPORTED_AS_RESEARCH_REQUIREMENT
NEGATIVE_RESULT with closed evidence
```

Negative results are first-class permanent knowledge when they close a bounded search line. They prevent future research from silently reopening an already-falsified assumption.

### TEMPORARY

A temporary note is still part of the active reasoning workspace.

It includes:

- open hypotheses;
- open questions;
- speculative bridges;
- architecture proposals not yet validated;
- open negative results;
- inconclusive claims;
- superseded current-state claims retained only for provenance.

Typical states:

```text
OPEN
INCONCLUSIVE
OPEN_NEGATIVE_RESULT
SUPERSEDED
```

Temporary does **not** mean disposable. IDs remain permanent and files are not deleted merely because a claim is open or superseded.

## Canonical storage rule

Canonical files remain in:

```text
research-lab/zettelkasten/notes/S3-ZK-*.md
```

The lifecycle split is represented by authoritative navigation indexes:

```text
research-lab/zettelkasten/permanent/INDEX.md
research-lab/zettelkasten/temporary/INDEX.md
```

Do not duplicate or move note bodies into those directories.

## Promotion gate: TEMPORARY -> PERMANENT

A note may be promoted only when all applicable fields are known:

```text
ATOMIC_CLAIM=
EVIDENCE=
SCOPE=
FALSIFIER_OR_REOPEN_CONDITION=
PROVENANCE=
CONFLICT_RECONCILIATION=
```

For correctness claims also require an appropriate correctness oracle, such as semantic reasoning, verifier evidence, differential tests, native validation, or another explicitly justified proof boundary.

For performance claims, structural improvement alone is insufficient. Runtime evidence must remain separate from legality and structural realization.

For literature-derived notes, source claims and S3 inference must remain distinguishable.

## Demotion / supersession

A previously permanent note can become non-current if later evidence invalidates the current-state interpretation.

Do not delete it.

Instead:

1. mark the note `SUPERSEDED` or narrower scoped status;
2. move its lifecycle entry to the temporary/superseded section;
3. link the replacing note;
4. preserve the original evidence window.

A bounded historical claim that remains true for its original SHA/corpus may remain permanent with `SCOPE=HISTORICAL_BOUNDED` even when the compiler later changes.

## Scope vocabulary

Recommended scope labels:

```text
GENERAL
CORRECTNESS_INVARIANT
RESEARCH_REQUIREMENT
RESEARCH_MODEL
CORPUS_SCOPED
SHA_SCOPED
HISTORICAL_BOUNDED
CAMPAIGN_SCOPED
```

## Insight candidates

Second-order syntheses must begin as temporary candidates.

Do not allocate a permanent `S3-ZK-*` ID merely because a synthesis is plausible.

Use:

```text
research-lab/zettelkasten/temporary/INSIGHT_CANDIDATES.md
```

A candidate receives a normal monotonic Zettel ID only when it is written as an atomic note with provenance, scope, falsifier and a clear promotion/experiment path.

## Research rule

```text
IDEA != CLAIM
CLAIM != PROOF
PROOF != REALIZABLE_OPTIMIZATION
REALIZABLE_OPTIMIZATION != PROFITABLE_OPTIMIZATION
```

Lifecycle separation exists to keep those layers explicit.
