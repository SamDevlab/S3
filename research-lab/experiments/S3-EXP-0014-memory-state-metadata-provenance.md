# S3-EXP-0014 - Memory-State Metadata Provenance

STATUS=SUPPORTED_FOR_P4_JSMN_STATIC_ORIGIN / DYNAMIC_NECESSITY_OPEN
RELATED_ZETTEL=S3-ZK-0004, S3-ZK-0021, S3-ZK-0022, S3-ZK-0027, S3-ZK-0030, S3-ZK-0032

## Exact metric

The P4 probe counted every native line containing `byte ptr [rbp`. A region-
aware independent analyzer reproduced `5638` in both RA modes and decomposed
it as:

```text
register initialized-state bytes = 4589
memory initialized-state bytes   = 837
trit payload bytes               = 212
```

## Causal result

The physical state bytes first appear in x86-64 frame layout and emitter
helpers. The state is semantically connected to initialization and immutable
write checks, but its exact proof-reuse opportunity is not measured.

## Falsifier and next step

The hypothesis that initialization-state materialization dominates would be
falsified by dynamic traces showing low hot-path weight or a larger mandatory
ABI/reference family. Obtain observer-aware dynamic weighting before choosing a
production transformation.
