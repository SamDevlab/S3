# ADR-0018: Postfix and qualified name resolution

- Status: accepted
- Date: 2026-08-01

## Context

S3 already has several postfix-like expression forms: calls, array indexing,
static text indexing, enum variant access, and record field access. The parser
currently treats some of these forms as special cases, while module support from
Milestone 0.99 deliberately avoided qualified source calls.

Milestone 1.02-B needs a single language contract for chained postfix
expressions before parser and semantic work can safely expand composition. The
same surface syntax must support:

- `module.function(args)`;
- `module.Enum.Variant`;
- `Enum.Variant`;
- `record_value.field`;
- `array[index]`;
- mixed chains such as `records[0].field`.

The parser must stay syntax-only. It must not depend on the symbol table to know
whether `A.B` is a module-qualified symbol, an enum variant, or a record field.

## Decision

S3 uses one uniform postfix grammar:

```text
postfix-expression = primary-expression postfix-suffix*
```

The `.` suffix is parsed as uniform member access: `MemberAccess(base, name)`.
The current implementation may keep the existing concrete compatibility name
`FieldAccessExpression`, but the architectural meaning is member access, not
record-only field access.

S3 does not introduce a separate parser-level `QualifiedName` expression. A
qualified name is a semantic result of member access over module and type
symbols, not a syntactic category that the parser resolves.

The call suffix applies to the current postfix expression. Therefore
`module.function(args)` is parsed as member access followed by a call suffix.
Semantic analysis decides whether the current postfix value is callable.

## Semantic resolution

Semantic analysis owns the distinction between:

- module symbol plus exported member;
- enum type symbol plus variant;
- record runtime value plus field;
- invalid member access on scalars, arrays, static text, enum values, or
  functions.

A local runtime binding in expression position wins over a module or type root
with the same name. There is no parser fallback based on symbol-table state, and
there is no lowering fallback that reinterprets a failed record-field lookup as
a module or enum access.

## Lowering boundary

Qualified names are resolved before lowering. The backend receives resolved
function, enum, record, and field identities; it does not parse dotted source
names.

This decision preserves the existing public IR, S3 Assembly, diagnostics schema,
native ABI, and optimizer contracts. Any implementation detail needed to carry
resolved identities remains internal unless a later ADR explicitly promotes it
to a public format.

## Consequences

Positive consequences:

- one postfix model covers calls, indexing, member access, qualified modules,
  enum variants, and record fields;
- chained expressions become a parser composition problem rather than a list of
  special cases;
- the parser remains independent from semantic symbol tables;
- lowering has a single source of truth: the semantic model;
- future cross-module nominal type access has a clear syntax boundary.

Negative consequences:

- semantic analysis must represent symbol-valued intermediate postfix results;
- existing `FieldAccessExpression` naming may remain temporarily misleading
  until implementation cleanup catches up;
- diagnostics must distinguish syntax member access from semantic categories.

## Alternatives considered

**Introduce separate `QualifiedName` and `MemberAccess` parser nodes.** Rejected
because the parser would either need symbol-table knowledge or would need to
guess based on surface shape. That would make `module.Enum.Variant` and
`record.field.subfield` harder to compose correctly.

**Keep the one-suffix parser model.** Rejected because it cannot represent
nested postfix expressions such as `module.function(args)`, `records[0].field`,
or future chains without adding more special cases.

**Resolve dotted names late in lowering.** Rejected because lowering would
duplicate semantic logic, risk masking semantic errors, and make backend naming
rules part of source-language meaning.

## Compatibility

Existing valid programs remain valid. This ADR does not add new public opcodes,
IR instructions, assembly directives, ABI forms, or diagnostics schema fields.
Runtime behavior changes only when later implementation milestones enable the
syntax described here.
