# S3-EXP-0015 — SSA destruction vs memory-state metadata staging

STATUS=PLANNED

RELATED_ZETTEL=

```text
S3-ZK-0006
S3-ZK-0009
S3-ZK-0027
S3-ZK-0030
S3-ZK-0031
```

## Question

After P4 enabled global value residency by default, how much residual repeated memory-state traffic is introduced by:

```text
SSA destruction / phi lowering
```

versus:

```text
later initialization/memory-validity metadata staging?
```

## Required separation

Measure independently:

```text
ORDINARY_VALUE_FRAME_TRAFFIC
PHI_EDGE_COPY_TRAFFIC
LOOP_PHI_TRAFFIC
SSA_DESTRUCTION_METADATA_TRAFFIC
INITIALIZATION_METADATA_TRAFFIC
MEMORY_VALIDITY_METADATA_TRAFFIC
TRUE_RA_SPILLS
CALL/ABI_TRAFFIC
```

Do not label unknown frame traffic as spills.

## Method

Trace a bounded real-value corpus through:

```text
SSA
-> SSA destruction
-> Assembly IR
-> allocation input/output
-> emitter metadata/state
-> native disassembly
```

Use loop/diamond/phi/call probes plus jsmn hot values.

## Falsifier

If SSA destruction contributes only a small residual share, do not make P5 an SSA rewrite merely because the post-P4 recommendation mentioned it.

If late metadata staging dominates, P5 should target that earlier/later causal layer instead.

## Gate

Return at minimum:

```text
PRIMARY_RESIDUAL_INTRODUCTION_LAYER=
SSA_DESTRUCTION_SHARE=
INITIALIZATION_METADATA_SHARE=
MEMORY_VALIDITY_SHARE=
TRUE_RA_SPILL_SHARE=
UNKNOWN_SHARE=
RECOMMENDED_P5_TARGET=
```
