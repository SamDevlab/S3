# S3-EXP-0013 — Compiler information-loss boundary audit

STATUS: PLANNED

RELATED_ZETTEL:

```text
S3-ZK-0009
S3-ZK-0021
S3-ZK-0022
S3-ZK-0027
```

## Question

Which useful properties of a logical value are preserved, derivable or irreversibly lost at each major S3 lowering boundary?

## Properties

Start with:

```text
LOGICAL_IDENTITY
TYPE
TRIT_SEMANTICS
VALUE_EQUIVALENCE
LOCATION_FLEXIBILITY
REPRESENTATION_FLEXIBILITY
RANGE_FACTS
PROVENANCE
MEMORY_VALIDITY
CROSS_BLOCK_LIVENESS
REMATERIALIZABILITY
```

## Output

For >=50 real values build:

```text
value x property x compiler-boundary ->
  PRESERVED | DERIVABLE | LOST | INTENTIONALLY_DISCARDED | UNKNOWN
```

Record the earliest unnecessary loss and correlate it with emitted frame/conversion/control traffic.

## Guardrail

Information-theoretic entropy is optional and only legal if an explicit probability model is justified. Deterministic recoverability/cardinality metrics are the default.
