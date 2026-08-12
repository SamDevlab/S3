# S3-EXP-0009 — Map current S3 ternary semantics and lowering

STATUS: PLANNED

RELATED_ZETTEL:

```text
S3-ZK-0016
S3-ZK-0017
S3-ZK-0023
```

## Question

What exact semantic truth tables/algebra does current S3 `trit` implement, and where is that semantic value first collapsed to a physical encoding?

## Work

Trace source/semantic/IR/Assembly/native behavior for every current unary/binary/relational trit operation.

Record:

```text
SOURCE_OPERATION
SEMANTIC_TABLE
IR_FORM
ASSEMBLY_FORM
NATIVE_ENCODING
FIRST_PHYSICAL_ENCODING_LAYER
CONVERSIONS
BRANCHES
```

## Falsifier

If current S3 semantics already require one canonical physical representation at all relevant boundaries, document the exact requirement rather than assuming representation polymorphism is useful.
