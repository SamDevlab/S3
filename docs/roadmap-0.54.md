# Architecture Specification S3 0.54 - Compile-Time Static Text Concatenation

## Status

Implementation complete locally; CI validation pending through the 0.54 Draft PR.

This milestone implements compile-time, literal-only static text concatenation.
It does not implement runtime concatenation, dynamic strings, heap allocation,
garbage collection, FFI, libc integration, public pointers, ABI changes, or any
new runtime string model.

## Context

Milestone 0.53 made `string` a first-class source type for static, immutable
text values. A string value is represented as a deterministic static handle
that resolves to UTF-8 bytes stored for the lifetime of the program. The 0.53
pipeline carries these handles through semantic analysis, IR `CONST_STR`, S3
Assembly `.data` plus `TCONST_STR`, hosted execution, and x86-64 native
read-only data.

Milestone 0.53 deliberately left string concatenation out of scope. Milestone
0.54 accepts `string + string` only when the whole expression is directly formed
from string literals and `+`.

## Motivation

The next useful text operation for compiler migration work is not dynamic text
construction. It is compile-time composition of fixed tokens such as:

```s3
message: string = "TRET " + "r1"
```

This should be equivalent to:

```s3
message: string = "TRET r1"
```

The compiler must intern only the final static text value. No runtime opcode,
runtime allocation, runtime buffer, or public pointer is needed.

## Existing Architecture

The existing codebase already provides the following foundation:

- The lexer recognizes string literals and the parser already parses `+` as
  `BinaryExpression(BinaryOperator.ADD, left, right)` using left-associative
  additive precedence.
- The AST has `StringLiteral`, `BinaryExpression`, and `TypeName.STRING`.
- Semantic analysis assigns `StringLiteral` the type `string` and currently
  rejects all binary operations whose operand type is `string`.
- `decode_static_text` decodes supported escapes (`\\`, `\"`, and `\n`) and
  normalizes newlines before UTF-8 encoding.
- `collect_static_string_literals` assigns static IDs as `s0`, `s1`, ... in
  first occurrence order and deduplicates by literal value.
- Lowering emits `IRStaticString` entries and `IROpcode.CONST_STR` for string
  literals.
- The optimizer folds numeric IR operations only. It is optional and must not
  be required for language correctness.
- Assembly, the emulator, and the x86-64 backend support static string handles
  but reject numeric opcodes such as `TADD` over string registers.

## Constant Expression Definition

A 0.54 constant static text expression is an AST expression that can be fully
resolved to decoded static text during compilation without reading runtime
state.

Included expression forms:

- `StringLiteral`
- `BinaryExpression(BinaryOperator.ADD, left, right)` where both `left` and
  `right` are constant static text expressions
- parenthesized expressions, because the parser preserves them only through the
  nested expression shape

Excluded expression forms:

- identifiers, including immutable string bindings
- mutable bindings
- parameters
- function calls
- match expressions
- index expressions
- `len(...)`
- unary expressions
- any numeric, array, or runtime value

This means the conservative 0.54 rule is: only trees formed directly from
string literals and `+` can participate.

## Binding Decision

Immutable bindings do not participate in 0.54 constant concatenation.

The following remains out of scope:

```s3
prefix: string = "TRET "
message: string = prefix + "r1"
```

This is intentionally conservative. Supporting immutable bindings would require
a constant-propagation contract across scopes, shadowing, assignment analysis,
and possibly function boundaries. The current infrastructure has local integer
constant helpers for selected semantic checks, but it does not expose a general
constant-value environment for string expressions. 0.54 should avoid adding that
risk.

## Syntax

No new syntax is introduced.

The milestone reuses the existing additive operator:

```s3
message: string = "TRET " + "r1"
```

The grammar remains the existing declaration grammar:

```s3
name: string = expression
mut name: string = expression
```

No `let` keyword is introduced.

## Semantics

The `+` operator is accepted for `string` only when the whole expression is a
constant static text expression as defined above.

Examples accepted by 0.54:

```s3
message: string = "TRET " + "r1"
value: string = "a" + "b" + "c"
empty_left: string = "" + "a"
empty_right: string = "a" + ""
empty_both: string = "" + ""
unicode_letters: string = "á" + "β"
unicode_emoji: string = "😀" + "S3"
grouped_left: string = ("a" + "b") + "c"
grouped_right: string = "a" + ("b" + "c")
escaped: string = "line\n" + "next"
```

The examples above resolve to a single static string value before runtime.

Examples rejected by 0.54:

```s3
mut name: string = "r1"
message: string = "TRET " + name
```

```s3
fn join(name: string) -> string:
    return "TRET " + name
```

```s3
bad1: string = "x" + 1
bad2: string = 1 + "x"
bad3: string = "x" + [-1, 0, 1]
```

The result type of an accepted constant static text concatenation is `string`.
It may be used wherever 0.53 already allows a `string` value: local bindings,
mutable bindings, helper function arguments, and helper function returns. Native
public `main -> string` remains rejected under the existing 0.53 rule.

## Compilation Model

The recommended implementation is folding during semantic or lowering
preparation, before the IR needs to represent the operation.

### Approach A - Folding before IR

The compiler resolves the AST subtree to one decoded static text value before
IR generation. Lowering then sees either an equivalent folded value or a helper
result that points to the final interned string.

Advantages:

- clearest language contract
- no runtime operation can leak into IR
- no dependency on optional optimization
- verifier, Assembly, emulator, and native backend remain unchanged

Risk:

- requires a small constant static text evaluator in the front end or in the
  lowering boundary

### Approach B - Folding during lowering

Lowering recognizes a constant static text expression, concatenates decoded
text, interns the final result, and emits only `CONST_STR`.

Advantages:

- close to the existing static string table and `CONST_STR` emission
- avoids a new IR opcode
- avoids changes to Assembly and runtime

Risk:

- semantic analysis must still validate the expression and reject runtime
  operands before lowering

### Approach C - Temporary IR and optimizer

The IR would represent string concatenation temporarily, and the optimizer
would be required to remove it.

Rejected for 0.54.

The lowering output must not depend on an optional optimization pass to remove
an operation that the runtime does not support. This approach would add verifier
surface, test burden, and an avoidable failure mode for O0 builds.

### Chosen Direction

Use the narrow form of Approach B: validate constant-only string concatenation
in semantic analysis and ensure lowering emits only the final interned
`CONST_STR`.

No IR concatenation opcode is introduced.

## Layer Impact

### Lexer

No change expected. String literal tokens and `+` already exist.

### Parser

No change expected. The parser already builds left-associative
`BinaryExpression` nodes for `+`.

### AST

No new node is required. 0.54 reuses `BinaryExpression` with
`BinaryOperator.ADD`.

### Semantic

Semantic analysis must distinguish two cases:

- accept `string + string` only when the entire expression is a constant static
  text expression;
- reject any string concatenation that depends on identifiers, parameters,
  calls, mutable bindings, or other runtime values.

Semantic analysis remains responsible for operand type errors such as
`string + tryte` and `tryte + string`.

### Diagnostics

Use the diagnostics defined below.

### Lowering

Lowering must emit exactly one static string handle for the final folded
content. It must not emit numeric `ADD`, string `ADD`, or any temporary runtime
operation for accepted concatenations.

### IR

IR continues to use `IRType.STRING`, `IRStaticString`, and `IROpcode.CONST_STR`.
No string concatenation opcode is added.

### Optimizer

The optimizer may remain unchanged. Correct compilation must not require O1 or
any optional pass.

### Assembly

No new instruction is expected. The final string appears in `.data` as a normal
static string entry and is loaded with `TCONST_STR`.

### Emulator

No new runtime operation is added. The emulator executes only the resulting
`TCONST_STR` and the existing string handle movement/call/return behavior.

### Backend x86-64

No ABI change is introduced. The backend emits the final folded text in
read-only static data and loads its address using the existing `TCONST_STR`
path.

### Tests

Tests must cover parser shape, semantic acceptance and rejection, deterministic
folding, static table interning, IR shape, Assembly output, emulator behavior,
and native read-only data behavior without adding runtime concatenation.

## Diagnostics

Prefer reusing existing public diagnostics unless implementation proves a new
code is necessary:

- `S3E_SEMANTIC_TYPE_MISMATCH` for incompatible operands such as `string +
  tryte`, `tryte + string`, `string + trit`, or `string + array`.
- `S3E_SEMANTIC_UNSUPPORTED_STRING_OPERATION` for string concatenation that is
  syntactically string-based but not compile-time constant, such as `"TRET " +
  name`.

If future implementation needs sharper tooling semantics, a later PR may
propose a dedicated diagnostic. This specification does not require one.

## Determinism and Interning

Concatenation operates on decoded static text content:

1. Each literal is decoded with the existing static text rules.
2. Newlines are normalized according to `decode_static_text`.
3. The decoded text pieces are concatenated in AST evaluation order.
4. The final text is encoded as UTF-8 for metadata and backend emission.

Empty strings are valid operands and contribute zero bytes.

Unicode is preserved as decoded text and encoded deterministically as UTF-8.
Escapes are decoded before concatenation, so `"a\n" + "b"` produces the same
content as `"a\nb"` after decoding.

The final result participates in the same static interning contract as 0.53
strings. Identical final contents deduplicate within a module:

```s3
first: string = "a" + "b"
second: string = "ab"
```

Both resolve to content `ab` and should share the same static table entry when
they appear in the same module. The specification requires deterministic IDs
according to first occurrence of the final interned content, but it does not
require a specific numeric ID in isolation.

Internal identity remains the static table handle. Source programs still cannot
observe physical addresses.

## Included Scope

- `+` for fully compile-time static text concatenation
- two string literals
- two or more literals through left association
- grouped literal-only expressions
- empty strings
- Unicode text
- supported escapes
- deterministic deduplication of the final result
- use of the folded result in bindings, arguments, and returns where 0.53
  already permits `string`
- equivalent behavior in hosted and native backends because both see only the
  final `CONST_STR`

## Excluded Scope

- immutable binding participation in concatenation
- mutable binding participation in concatenation
- parameters or runtime values in concatenation
- function calls in constant static text expressions
- dynamic string construction
- heap allocation
- garbage collection
- incremental string builders
- interpolation
- numeric formatting
- comparison
- indexing
- `len(string)`
- byte mutation
- string-to-tryte, tryte-to-string, string-to-trit, or trit-to-string
  conversion
- FFI
- libc
- public pointer exposure
- ABI changes
- runtime concat opcodes

## Acceptance Criteria

1. `"a" + "b"` produces content equivalent to `"ab"`.
2. `"a" + "b" + "c"` produces content equivalent to `"abc"`.
3. `"a" + ("b" + "c")` and `("a" + "b") + "c"` produce the same content.
4. `"" + "a"`, `"a" + ""`, and `"" + ""` are accepted.
5. Unicode text is concatenated by decoded content and emitted as UTF-8.
6. Supported escapes are decoded before concatenation.
7. The final result is deduplicated in the static table.
8. No runtime concatenation operation appears in IR, Assembly, emulator, or
   native backend output.
9. No new runtime opcode is required.
10. O0 compilation remains correct without optional optimizer passes.
11. Incompatible operands are rejected.
12. Runtime-dependent string operands are rejected.
13. Hosted emulator and x86-64 native backend observe the same final static
    value.
14. The 0.53 test suite remains green.
15. No ABI change, heap allocation, GC, FFI, libc dependency, or public pointer
    exposure is introduced.

## Test Matrix

| Area | Required coverage |
| --- | --- |
| Parser | Existing `+` parsing continues to produce `BinaryExpression` trees. |
| Semantic accept | Literal-only concatenation in bindings, arguments, and helper returns. |
| Semantic reject | Identifiers, mutable bindings, parameters, calls, arrays, and numeric operands. |
| Escapes | Decoding before concatenation, including newline and quote/backslash escapes. |
| Unicode | Multi-byte UTF-8 text preserved in final metadata. |
| Empty string | Empty operands and empty final text. |
| Interning | `"a" + "b"` deduplicates with `"ab"` in one module. |
| IR | Only `CONST_STR` for the final value; no concat opcode. |
| Assembly | `.data` contains the final text and code uses `TCONST_STR`. |
| Emulator | Existing string handle behavior observes the folded result. |
| Native | `.rodata` contains the final text; no ABI or runtime helper change. |
| Regression | 0.53 static text tests remain green. |

## Risks

- Accidentally accepting identifiers as constants without a full
  constant-propagation contract.
- Letting string concatenation lower to numeric `ADD` or Assembly `TADD`.
- Making O0 correctness depend on O1 constant folding.
- Deduplicating by raw spelling instead of decoded final content.
- Changing 0.53's static string ID determinism unintentionally.
- Expanding into formatting, interpolation, comparison, indexing, or length
  under the same milestone.

## Rejected Alternatives

### Runtime Concatenation

Rejected because it requires a runtime representation for newly constructed
text, which implies allocation, buffers, ownership, or host dependencies outside
the 0.54 scope.

### Immutable Binding Propagation

Rejected for 0.54 because the current infrastructure does not provide a general
constant string environment. It can be reconsidered after a separate constant
propagation design.

### Temporary IR Concat Opcode

Rejected because the runtime does not support concat and O0 builds must remain
correct without optimizer elimination.

### Assembly-Level Concat Instruction

Rejected because accepted 0.54 programs should reach Assembly as ordinary
static strings loaded by `TCONST_STR`.

## Implementation Summary

The 0.54 implementation keeps the runtime and backend model unchanged:

- semantic analysis accepts only literal-only `BinaryOperator.ADD` trees whose
  whole expression is compile-time static text;
- semantic analysis rejects identifiers, bindings, parameters, calls, arrays,
  numeric operands, and partial static/dynamic trees;
- lowering evaluates the accepted AST subtree to decoded text and emits one
  final `CONST_STR`;
- the static string table interns by decoded final content, so `"a" + "b"` and
  `"ab"` deduplicate;
- IR, S3 Assembly, emulator, optimizer, and x86-64 backend do not gain concat
  opcodes, helpers, ABI changes, heap allocation, GC, FFI, libc dependencies,
  or public pointer exposure.

## Composite PR Plan

The implementation PR is split into small reviewable commits:

1. `feat(0.54): define constant static text concatenation semantics`
2. `feat(0.54): fold constant text expressions before IR`
3. `test(0.54): cover semantic acceptance and rejection`
4. `test(0.54): cover IR and static table determinism`
5. `test(0.54): cover assembly and emulator behavior`
6. `test(0.54): cover native static text concatenation`
7. `docs(0.54): record implementation boundaries`

The PR must not retroactively change the delivered scope of 0.53.

## Definition of Done

0.54 is complete only when:

- this specification is implemented without widening the runtime string model;
- literal-only concatenation folds to a final static string before runtime;
- no concat opcode exists in IR or Assembly;
- semantic diagnostics reject runtime-dependent concatenation;
- deterministic interning is covered by tests;
- emulator and native behavior remain equivalent for the folded result;
- all 0.53 static text tests and repository regression checks pass;
- documentation marks 0.54 implemented after code and local validation are
  complete, with CI status tracked by the Draft PR.
