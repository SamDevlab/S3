# Stage 04 — Expression lowering: close S1 and S2

## Goal

Implement a real semantic expression parser/lowerer for the Stage1 candidate and close typed values plus instruction def/use.

## Authoritative current operator scope

Do **not** invent operators that are absent from the current S3 AST/IR.

Current scalar operator coverage relevant to this stage is:

- unary negation `-`;
- unary inversion `~`;
- binary addition `+`;
- subtraction `-` using the existing architecture (addition of inverted RHS where applicable);
- tritwise minimum `&`;
- tritwise maximum `|`;
- ternary compare `<=>`;
- relational `==`, `!=`, `<`, `<=`, `>`, `>=`.

There is currently **no multiplication, division, or remainder operator** in the current AST/IR. Do not implement `*` as arithmetic multiplication. `*` may appear in other language features such as reference dereference, which is outside this Stage04 minimal scalar arithmetic requirement unless the existing candidate already supports it for an explicitly required source.

For precedence, use repository-supported expressions such as the V0.6 parser test:

```s3
mut res: trit = 1 <=> 2 < 3
```

whose AST is expected to parse as `(1 <=> 2) < 3`.

## Required expression coverage

- integer literals, including negative and wide literals;
- trit/tryte/i64 typing used by canonical Stage1;
- identifier lookup through lexical bindings;
- unary `-` and `~` as required by current source/operator scope;
- supported binary numeric/tritwise/comparison operations with correct precedence;
- casts/conversions actually used by canonical Stage1;
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
- lexical token counts are not semantic instruction counts;
- unsupported language operators must fail closed rather than being silently invented;
- `*` must never be treated as multiplication under the current language contract.

## Required fixtures

- return literal;
- negative/wide literal;
- return parameter;
- local initialized from literal/parameter;
- `a + b`;
- V0.6 precedence/comparison case equivalent to `1 <=> 2 < 3`;
- focused relational comparison;
- reassignment (`mut value ...; value = value + ...`);
- nested expression using only supported current operators;
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
