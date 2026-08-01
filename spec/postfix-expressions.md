# S3 postfix expressions and qualified resolution

Status: normative and implemented for Milestone 1.02-B.

This document defines the source-language contract for composable postfix
expressions. It does not change any public IR, S3 Assembly, ABI, diagnostic
schema, or native interface.

## Scope

The contract covers:

- function calls;
- array and static-text indexing;
- member access through `.`;
- qualified module symbols;
- enum variants;
- record field access.

The parser must not consult the symbol table. It recognizes the syntactic shape
of a postfix chain. Semantic analysis assigns meaning to each suffix.

## Grammar

Postfix expressions compose from a primary expression followed by zero or more
postfix suffixes:

```ebnf
expression         = relational ;
unary              = ("~" | "-"), unary | postfix-expression ;
postfix-expression = primary-expression, { postfix-suffix } ;
postfix-suffix     = call-suffix | index-suffix | member-suffix ;
call-suffix        = "(", [ argument-list ], ")" ;
index-suffix       = "[", expression, "]" ;
member-suffix      = ".", identifier ;
argument-list      = expression, { ",", expression } ;
```

Primary expressions include integer literals, string literals, identifiers,
record construction expressions, `match` expressions, `len(...)`, and
parenthesized expressions.

A record construction expression is a primary expression with named field
initializers, for example:

```s3
Point(x: 1, y: 2)
```

S3 does not support named function arguments in this milestone, so the named
field shape is reserved for record construction.

Dotted names are not a separate grammar production. Source such as
`math.abs_tryte(value)`, `Color.Red`, and `pkg.Color.Red` is parsed as a
postfix expression with one or more member suffixes, followed by a call suffix
when applicable.

## Precedence and associativity

Postfix suffixes bind tighter than unary and binary operators.

All postfix suffixes associate from left to right:

```s3
module.Enum.Variant
records[0].field
factory()(0)
```

Unary operators apply after the complete postfix expression is parsed:

```s3
-value.field
```

is parsed as negation of `value.field`, not as field access on `-value`.

Binary operators consume complete postfix expressions as operands:

```s3
a.b + c[0]
```

is parsed as `(a.b) + (c[0])`.

## Source spans

Each postfix node owns the span from the start of its base expression through
the end of its suffix. The suffix span remains available for diagnostics:

- call suffix: opening `(` through closing `)`;
- index suffix: opening `[` through closing `]`;
- member suffix: `.` through the member identifier.

Diagnostics should report the most specific useful span. For example, an
unknown field should point at the member suffix, while an invalid base should
point at the base expression when that is clearer.

## Evaluation order

Runtime-producing subexpressions are evaluated left to right:

1. evaluate the base expression;
2. apply the first suffix;
3. apply each following suffix in source order.

Arguments in a call suffix are evaluated left to right after the callee has
been resolved. Index expressions are evaluated after the target expression.

Qualified module and enum paths are compile-time symbol resolution and do not
produce runtime values. Record field access evaluates its record value before
the field projection.

## Semantic resolution

Semantic analysis is the single source of truth for the meaning of each postfix
suffix. Lowering must consume semantic decisions and must not reclassify a
postfix expression by repeating independent symbol lookup.

Member access uses the resolved category of the base:

| Base category | Member meaning |
| --- | --- |
| Module symbol | exported function or exported type member of that module |
| Enum type symbol | enum variant |
| Record runtime value | record field |
| Scalar runtime value | semantic error |
| Array runtime value | semantic error for `.` |
| Static text runtime value | semantic error for `.` |
| Function symbol without call | semantic error except as a call callee |
| Unknown symbol | semantic error |

Resolution is deterministic. A local runtime binding in expression position wins
over a type or module root with the same name. There is no silent fallback from
one category to another after semantic analysis has selected a meaning or
reported an error.

## Calls

A call suffix is valid only when the current postfix value resolves to a
function symbol or a builtin callable accepted by the language.

Qualified calls are resolved before lowering:

```s3
math.abs_tryte(value)
```

The lowering pipeline receives the resolved function identity. It must not rely
on backend parsing of strings such as `math.abs_tryte`.

Record construction is not a call, even though it uses parentheses.

## Indexing

An index suffix is valid for arrays and static text values under the contracts
defined by their own specifications. It is invalid for modules, enum types,
enum values, records, scalar values, and function symbols unless a future
milestone explicitly extends those categories.

`len(...)` remains a dedicated language form. This contract does not define
method calls such as `value.len()`.

## Modules

Milestone 0.99 introduced module declarations and explicit function imports,
but it did not allow qualified source calls. This contract defines the syntax
and semantic boundary for qualified module access.

A module symbol is visible only through deterministic module graph resolution
and explicit language rules. Filesystem iteration order, backend names, and
host paths must not affect qualified resolution.

For this milestone, `module.function(args)` resolves to an exported function and
lowers to the compiler's deterministic internal function name. Qualified enum
variants such as `module.Enum.Variant` resolve when the module is visible
through an explicit import and the enum is declared in that module.
Cross-module nominal type imports and using imported record types directly in
consumer declarations are completed by Milestone 1.02-C; until then,
unavailable type members must be rejected semantically rather than guessed by
lowering.

## Enums

Enum variants are member accesses on enum type symbols:

```s3
Color.Red
```

Enums remain closed and have no payload in this contract. Variant resolution is
compile-time symbol resolution. The resulting enum value follows the existing
semantic and lowering rules for enum discriminants.

## Records

Record field access is member access on a record runtime value:

```s3
point.x
```

The field must exist on the resolved record type. Field projection does not
imply mutation, address-taking, methods, reflection, dynamic lookup, or deep
record equality.

Nested field chains become valid only when the record composition milestone
that owns the corresponding type shape is implemented.

The implemented 1.02-B contract supports record field reads from record
literals, local bindings, parameters, enum-valued fields, and single-field
record returns, including after qualified calls such as `module.make().field`.
Field assignment remains unsupported.

## Syntax errors

The parser should reject malformed postfix syntax before semantic analysis:

- missing closing `)` or `]`;
- missing member name after `.`;
- empty index suffix `[]`;
- dangling postfix separators;
- malformed record field initializer lists.

## Semantic errors

Semantic analysis should reject well-formed syntax with invalid meaning:

- calling a non-callable expression;
- indexing a non-indexable expression;
- accessing a member on a scalar, array, static text, enum value, or function
  value;
- referencing an unknown module member;
- referencing an unknown enum variant;
- referencing an unknown record field;
- using a qualified type member before that type is available in the importing
  module;
- attempting to use parser-only dotted syntax as a backend name.

## Lowering contract

Lowering consumes resolved semantic identities:

- function calls receive resolved function identities;
- enum variants receive resolved enum and variant identities;
- record fields receive resolved record and field identities;
- array/static-text indexes receive the resolved target kind.

Lowering may assume semantic analysis already rejected invalid postfix
expressions. It may not use exception-driven probing or backend name heuristics
to decide whether a member expression is a module reference, enum variant, or
record field.
