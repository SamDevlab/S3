# S3-ZK-0003 — Value representation may admit a residence lattice

```text
TYPE=HYPOTHESIS
STATUS=OPEN
CREATED=2026-08-12
```

## Atomic claim

The compiler may be able to represent knowledge about a logical value's available representations as a finite ordered abstract domain and solve it by conservative fixed-point analysis.

## Origin

```text
SOURCE_DERIVED + HYPOTHESIS
```

Lattice/fixed-point techniques are standard foundations for program analysis. The new S3 hypothesis is that **representation availability** itself is a useful analysis domain.

## Candidate facts

Possible facts include:

```text
DEAD
REGISTER_OR_VIRTUAL_VALID
MEMORY_VALID
BOTH_VALID
REMATERIALIZABLE
MUST_MATERIALIZE
UNKNOWN/CONFLICT
```

Do not assume these states form the correct lattice.

## Required proof work

Define:

```text
ORDER
BOTTOM
TOP
MEET/JOIN
TRANSFER FUNCTIONS
KILLS
BOUNDARY CONDITIONS
```

Then verify monotonicity and convergence.

## Connections

```text
[[S3-ZK-0002]] --motivates--> [[S3-ZK-0003]]
[[S3-ZK-0003]] --generalizes--> [[S3-ZK-0011]]
[[S3-ZK-0004]] --alternative-to--> [[S3-ZK-0003]]
```

## Falsifier

Find a common S3 representation condition whose safe confluence cannot be represented without making the domain either unsound or uselessly imprecise.

## Experiment

Prototype a tiny finite domain and property-test its order/join laws before connecting it to S3 IR.
