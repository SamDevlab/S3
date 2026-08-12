# S3-EXP-0014 — Memory-state metadata provenance

STATUS=PLANNED

RELATED_ZETTEL=

```text
S3-ZK-0004
S3-ZK-0021
S3-ZK-0022
S3-ZK-0027
S3-ZK-0030
```

## Motivation

P4 reduced direct value-related frame traffic but measured metadata accesses remained:

```text
5638 -> 5638
```

Residual production diagnosis:

```text
REPEATED_MEMORY_STATE_MATERIALIZATION
```

## Model

For each metadata-related memory operation, trace:

```text
native op
<- emitter state
<- Assembly IR / lowered metadata
<- SSA/initialization fact
<- semantic requirement
```

Classify origin as:

```text
INITIALIZED_STATE
MEMORY_VALIDITY
PHI_MERGE_STATE
LOOP_CARRIED_STATE
ABI_REQUIRED
REFERENCE_REQUIRED
FAILURE_PATH_REQUIRED
DUPLICATE_STATE_MATERIALIZATION
UNKNOWN
```

## Inputs

Use exact current production main after P4 and representative jsmn + focused CFG/state probes.

## Control

Do not modify production code during attribution.

## Measurement

Record:

```text
TOTAL_METADATA_ACCESSES
SEMANTICALLY_MANDATORY
ABI_MANDATORY
SSA_ORIGIN
PHI_ORIGIN
LOOP_ORIGIN
LATE_EMITTER_ORIGIN
DUPLICATE/AVOIDABLE
UNKNOWN
DYNAMIC_WEIGHT where defensible
```

## Falsifier

If the 5638 count is not actually dominated by repeated metadata-state realization, narrow/reject S3-ZK-0030 and identify the real source.

## Success

A production P5 target is not selected from this experiment until at least the dominant metadata category and earliest introduction layer are measured.
