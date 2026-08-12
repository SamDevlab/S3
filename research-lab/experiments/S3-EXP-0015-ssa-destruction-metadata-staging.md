# S3-EXP-0015 - SSA Destruction vs Memory-State Metadata Staging

STATUS=SUPPORTED_NEGATIVE_FOR_P4_JSMN_CORPUS / GENERALITY_OPEN
RELATED_ZETTEL=S3-ZK-0006, S3-ZK-0009, S3-ZK-0027, S3-ZK-0030, S3-ZK-0033

## Result

The exact O1 JSMN compilation has `34` dominator-confirmed backedges, but no
phi nodes, no phi edge copies and no critical edges. The `5638` byte-frame
population is therefore not SSA/phi traffic in this corpus. The explicit
out-of-SSA lowering path remains present in the compiler, so this is a
workload-scoped negative result rather than a deletion of the general
hypothesis.

## Falsifier and next step

The negative result would not generalize if a separate CFG with real phis
showed a dominant dynamic share. Run a focused phi-heavy synthetic corpus in
the future; do not select SSA as P5 without that evidence.
