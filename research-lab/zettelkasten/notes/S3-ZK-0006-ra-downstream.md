# S3-ZK-0006 — RA cannot repair logical-value identity already destroyed upstream

```text
TYPE=PERMANENT
STATUS=SUPPORTED
CREATED=2026-08-12
```

## Atomic claim

A frame access is a true register-allocation spill only if the allocator received the logical value as register-eligible and chose/was forced to place it in memory. Memory traffic introduced before RA is not evidence of allocator failure.

## Origin

```text
S3_CODE_INSPECTION + S3_MEASURED
```

P3 forensics established pre-RA/default-path frame canonicalization while true RA spills were not established as dominant.

## S3 implication

Before an RA milestone, prove:

```text
VALUE_SURVIVES_TO_RA=YES
CROSS_BLOCK_LIVENESS_AT_RA=VALID
MEMORY_NOT_ALREADY_REQUIRED=YES
RA_CREATED_SPILL=YES
DYNAMIC_SPILL_SHARE=SIGNIFICANT
```

## Connections

```text
[[S3-ZK-0006]] --supports--> [[S3-ZK-0001]]
[[S3-ZK-0009]] --explains--> [[S3-ZK-0006]]
```

## Falsifier

A post-transformation attribution showing most removable hot memory operations are generated directly by allocator spill decisions would shift the primary target to RA.
