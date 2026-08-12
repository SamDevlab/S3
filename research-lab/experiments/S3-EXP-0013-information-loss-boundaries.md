# S3-EXP-0013 - Compiler Information-Loss Boundary Audit

STATUS=SUPPORTED_FOR_INITIAL_CORPUS / CROSS_WORKLOAD_OPEN
RELATED_ZETTEL=S3-ZK-0009, S3-ZK-0021, S3-ZK-0022, S3-ZK-0027, S3-ZK-0028, S3-ZK-0032

## Input

Exact P4 production merge `a0b694f...` plus the external JSMN source used by
the P4 characterization. No source file was copied into production.

## Result

The IR initialization analyzer retains `UNINITIALIZED`, `INITIALIZED` and
`MAYBE_INITIALIZED` facts, but the native emitter reifies its own per-register
and per-memory byte flags. SSA identity and phi relations are intentionally
absent from Assembly IR. Residence/coherence is implicit in the physical
allocation and snapshot rules.

The physical-origin classification covered all `5638` target lines. Semantic
required/avoidable and dynamic shares remain unresolved by design.

## Falsifier and next step

This result would be falsified by a cross-workload trace showing the same byte
population is mainly ABI, reference or true-spill traffic. Add a provenance
trace across at least call-heavy, slice/reference and numeric workloads before
production promotion.
