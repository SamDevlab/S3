# S3 Zettelkasten

This is the durable research knowledge graph for S3 compiler work.

## IDs

Use monotonically increasing IDs:

```text
S3-ZK-0001
S3-ZK-0002
...
```

Never reuse an ID after deletion/rejection. Prefer deprecation notes over deletion.

## Lifecycle separation

Canonical note bodies remain in:

```text
notes/S3-ZK-*.md
```

Do not move or duplicate them merely to classify lifecycle. Stable IDs and historical links must remain intact.

Current lifecycle navigation:

```text
LIFECYCLE_POLICY.md
permanent/INDEX.md
 temporary/INDEX.md
 temporary/INSIGHT_CANDIDATES.md
```

Interpretation:

```text
PERMANENT = supported durable knowledge within an explicit scope
TEMPORARY = open, speculative, inconclusive or superseded current-state knowledge
```

A scoped negative result can be permanent. An attractive architecture proposal can remain temporary.

The lifecycle class is therefore epistemic, not a synonym for the note's `TYPE`.

## Note types

```text
SOURCE
PERMANENT
BRIDGE
QUESTION
HYPOTHESIS
EXPERIMENT
NEGATIVE_RESULT
ARCHITECTURE
```

## Status

```text
OPEN
SUPPORTED
REJECTED
INCONCLUSIVE
PROMOTED
SUPERSEDED
```

## Naming

```text
notes/S3-ZK-0001-location-flexibility.md
```

The ID is permanent; the descriptive slug may be improved later.

## Linking

Use wiki-style IDs in prose:

```text
[[S3-ZK-0001]]
```

Optionally annotate relationship:

```text
[[S3-ZK-0001]] --supports--> [[S3-ZK-0002]]
```

## Rule

A note should be useful even if read years later without the original chat.

Therefore include:

- the atomic claim;
- source or origin;
- why it matters to S3;
- links;
- falsifier/experiment when applicable;
- current status.
