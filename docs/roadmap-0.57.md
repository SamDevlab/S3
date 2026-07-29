# Roadmap S3 0.57 - Compile-Time Static Text Constant Propagation

## Status

Implementation complete locally; Draft PR validation pending.

## Objective

Milestone 0.57 allows immutable `string` bindings whose initializer is fully
known at compile time to participate in the static text operations delivered by
0.54, 0.55, and 0.56:

- literal-only concatenation;
- `len(...)`;
- `==`;
- `!=`;
- initialization of another static string binding.

The milestone remains strictly compile-time. It does not introduce dynamic
strings, runtime concatenation, runtime equality, heap allocation, garbage
collection, ABI changes, FFI, libc integration, public pointers, new IR
opcodes, new Assembly instructions, emulator behavior, or backend behavior.

## Motivation

Static text operations become substantially more useful when fixed fragments
can be named and reused:

```s3
prefix: string = "hel"
suffix: string = "lo"
message: string = prefix + suffix
size: tryte = len(message)
same: trit = message == "hello"
```

All of these values are known during semantic analysis and can be lowered using
the existing static text model.

## Eligible Binding Definition

A binding is eligible for static text propagation only when:

- it is immutable;
- its declared type is `string`;
- its initializer is a compile-time static text expression;
- every identifier used by the initializer resolves to an already visible
  immutable static text binding;
- it does not depend on parameters, calls, mutable bindings, runtime values, or
  future declarations.

Mutable bindings remain runtime values even if their initializer is a literal.

## Architecture

Semantic analysis is the source of truth. It resolves identifiers through the
existing scoped binding stack, computes decoded logical text for eligible
immutable bindings, and stores that value in the semantic model by expression.

Lowering does not resolve symbols or reconstruct declaration history. It
queries the semantic model for the static text value associated with an
expression and then uses the existing static text evaluator for concatenation,
length, and equality.

## Scopes and Shadowing

The existing scope stack controls visibility. A local binding shadows an outer
binding because lookup already walks scopes from innermost to outermost.

Static text propagation is attached to the resolved binding and to the
expressions analyzed under that binding. It is not a global name table keyed
only by string names.

## Declaration Order and Cycles

Bindings are inserted into the current scope only after their initializer is
analyzed. This preserves the existing declaration-order rule:

- earlier immutable static text bindings may be used;
- future declarations are not visible;
- direct and indirect cycles that require forward references are rejected by
  existing unresolved-name diagnostics.

No compile-time execution or fixpoint solver is introduced.

## Semantics

The following become valid:

```s3
message: string = "hello"
size: tryte = len(message)

left: string = "hel"
right: string = "lo"
complete: string = left + right
same: trit = complete == "hello"
```

The following remain invalid:

```s3
mut message: string = "hello"
size: tryte = len(message)
```

```s3
fn identity(value: string) -> string:
    return value

message: string = identity("hello")
size: tryte = len(message)
```

## Lowering

For propagated static text, lowering emits the same forms already used by the
previous milestones:

- string values lower to the final interned static text handle and `CONST_STR`;
- `len(...)` lowers to numeric `CONST`;
- equality and inequality lower to `CONST trit`;
- no concat, length, or equality operation reaches IR.

## Interning

String values that exist as real source bindings continue to be materialized
when the current lowering path needs them. Text used only inside static
`len(...)` or static equality is not interned unnecessarily.

Intermediate text fragments remain unobservable and should not be added to the
static table unless the surrounding source binding itself requires a string
value.

## Diagnostics

The implementation reuses existing semantic diagnostics:

- unsupported string operation for runtime-dependent text operations;
- type mismatch for mixed operands;
- unresolved variable diagnostics for future references and unavailable names;
- immutable assignment diagnostics for mutation attempts.

No public diagnostic code is added.

## Excluded Scope

- mutable binding propagation;
- `tryte` or `trit` constant propagation;
- generic constant propagation;
- parameters;
- function calls;
- returns as compile-time values;
- interprocedural evaluation;
- runtime strings;
- runtime concatenation or equality;
- indexing, slicing, formatting, interpolation, lexicographic ordering;
- heap, GC, FFI, libc, public pointers, ABI changes;
- IR opcode, Assembly instruction, emulator, or backend changes.

## Test Strategy

Coverage should include:

- immutable string bindings in concatenation, `len`, equality, and inequality;
- chains of static string bindings;
- empty text, escapes, and Unicode;
- binding-to-binding initialization;
- shadowing and nested scopes;
- rejection of mutable bindings, parameters, calls, future references, unknown
  symbols, and mixed types;
- lowering to existing `CONST` and `CONST_STR` forms only;
- static string table behavior;
- regressions for 0.53, 0.54, 0.55, and 0.56.

## Future Work

Future milestones may specify broader constant propagation, runtime strings,
interprocedural constants, modules, text indexing, formatting, interpolation,
or lexicographic comparison. None of those are part of 0.57.
