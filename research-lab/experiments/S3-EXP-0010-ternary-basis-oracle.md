# S3-EXP-0010 — Ternary operation-basis synthesis oracle

STATUS: PLANNED

RELATED_ZETTEL:

```text
S3-ZK-0007
S3-ZK-0018
S3-ZK-0023
```

## Question

Can a small set of ternary primitives synthesize the current S3 trit operations with lower target cost than direct generic lowering?

## Model

Enumerate finite truth tables over the exact S3 trit domain. Search bounded expression DAGs built from candidate primitive sets. Use exact enumeration for tiny basis search and a backend cost function only after semantic completeness is proven.

## Measurements

```text
BASIS_SIZE
FUNCTIONS_COVERED
MAX_SYNTHESIS_DEPTH
X86_STATIC_COST
BRANCH_COST
CONVERSION_COST
CODE_SIZE
```

## Rule

Do not change S3 semantics to fit Łukasiewicz, Kleene, Post or another named system. First identify the exact existing semantics; named logics are comparison tools.
