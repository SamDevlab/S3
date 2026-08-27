# Stage 04 — Expression lowering: close S1 and S2

## Goal

Implement a real semantic expression parser/lowerer for the Stage1 candidate and close typed values plus instruction def/use.

## Required expression coverage

- integer literals, including negative and wide literals;
- trit/tryte/i64 typing used by canonical Stage1;
- identifier lookup through lexical bindings;
- unary operations;
- arithmetic/comparison binary operations with correct precedence;
- casts/conversions used by canonical Stage1;
- local initialization;
- assignment/reassignment;
- semantic loads/stores as required;
- instruction result values;
- deterministic instruction IDs;
- ordered O operand edges;
- exactly one R definition for each instruction result.

## Required invariants

- every use references a defined logical value;
- no semantic value ID is inferred from a physical array index unless the policy explicitly proves that index is a stable logical identity;
- scratch reuse cannot invalidate a previously emitted edge;
- lexical token counts are not semantic instruction counts.

## Required fixtures

- return literal;
- negative/wide literal;
- return parameter;
- local initialized from literal/parameter;
- `a + b`;
- precedence case such as `a + b * c`;
- comparison;
- reassignment;
- nested expression;
- shadowed identifier resolution.

## Exit gate

Run native candidate fixtures and strict v2 conformance.

Required:

```text
S1_TYPED_VALUES=PASS
S2_DEF_USE=PASS
FOCUSED_NATIVE_V2_CONFORMANCE=PASS_FOR_STAGE04_FIXTURES
Z_MASK_FOR_INCOMPLETE_PROGRAMS=<31 until S3/S4/S5 exist>
```

Do not fake `Z 31` just because S1/S2 passed.
