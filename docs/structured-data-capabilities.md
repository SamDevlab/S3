# Structured Data Capability Inventory

## Purpose

This inventory maps the structured data support S3 needs before future
Python-to-S3 migration work can safely represent compiler data in S3.

It does not implement records, structs, enums, pattern matching, string runtime
support, or self-hosting. Its goal is to identify the smallest data model that
would let a future Assembly renderer subset represent program, function, block,
instruction, operand, and optional source metadata shapes without losing
determinism.

## Current state

Confirmed current support:

| Feature | Current support | Evidence | Notes |
| --- | --- | --- | --- |
| Records or structs | Not supported as S3 source-level data | `bootstrap/s3/lexer.py`, `bootstrap/s3/parser.py`, `bootstrap/s3/ast.py`, `spec/grammar.ebnf` | Python dataclasses model compiler internals, but there is no user syntax for record values or field access. |
| Enums or sum types | Not supported as S3 source-level data | `bootstrap/s3/ast.py`, `bootstrap/s3/assembly.py`, `bootstrap/s3/ir.py` | Python enums exist for internal compiler data such as types, opcodes, tokens, and diagnostics. |
| Variants or tagged unions | Not supported | `bootstrap/s3/ast.py`, `bootstrap/s3/parser.py` | No variant payload syntax or semantic model was found. |
| Pattern matching | Not supported generally | `bootstrap/s3/parser.py`, `bootstrap/s3/semantic.py`, `tests/test_parser_match_v0_6.py` | S3 has a v0.6 `match` surface for ternary control flow only; arms are integer labels and semantic analysis restricts them to `-1`, `0`, and `1`. |
| Tuples | Not supported as source values | `bootstrap/s3/ast.py`, `bootstrap/s3/parser.py`, `spec/grammar.ebnf` | Python tuples are used internally for immutable compiler data. |
| Named fields | Not supported as source values | `bootstrap/s3/ast.py`, `bootstrap/s3/parser.py` | Names exist for variables, functions, parameters, labels, and Python dataclass fields, but not for source-level structured values. |
| Arrays | Supported with limitations | `docs/array-capabilities.md`, `bootstrap/s3/ast.py`, `bootstrap/s3/semantic.py`, `bootstrap/s3/lowering.py` | Fixed-size arrays exist and lower to memory, but they are not first-class values. |
| Strings | Reserved, no runtime support | `docs/minimal-string-contract.md`, `bootstrap/s3/lexer.py`, `bootstrap/s3/parser.py` | String literals are tokenized and then rejected by the parser with a reserved-syntax diagnostic. |

Useful current alternatives are fixed-size arrays, scalar variables, function
calls, ternary `match`, and host-side Python data while the compiler remains the
reference implementation.

## Why structured data is required

The Assembly renderer subset needs to preserve named relationships that are
already explicit in the Python model:

- `AssemblyProgram` needs a version and an ordered list of functions.
- `AssemblyFunction` needs a name, return type, parameters, register
  declarations, blocks, memory declarations, and a body.
- `AssemblyInstruction` needs an opcode, operands, optional immediate values,
  optional labels, optional callee names, optional memory references, and
  optional source metadata.
- Operands need to distinguish registers, constants, labels, function names,
  and memory names.
- Source metadata needs line, column, and offset fields when present.

Arrays alone preserve order, but they do not preserve names, invariants, or
variant payload meaning. Strings alone can represent output text and names, but
they do not encode the structure of a program or instruction safely.

## Existing alternatives

| Alternative | Advantage | Risk | Fit for Assembly renderer subset |
| --- | --- | --- | --- |
| Parallel arrays | Reuses existing fixed-size arrays and keeps each field homogeneous | Array lengths can drift, indexes become implicit contracts, and relationships are hard to validate | Possible for a tiny fixture, fragile beyond a prototype |
| Arrays of numeric codes | Represents opcodes, operand kinds, and type tags with scalar values | Numeric tags are not self-describing and can accept invalid combinations | Usable as a temporary enum substitute only with strict conventions |
| Manual flattening | Avoids needing nested structures by expanding fields into local variables | Duplicates rendering logic and makes instruction lists hard to iterate | Adequate for one hand-written fixture, poor for a reusable renderer |
| Convention-based scalar groups | Keeps data explicit in variable names such as `inst0_opcode` and `inst0_reg0` | Does not scale and cannot be passed as one value | Good for smoke tests, not for a real component boundary |
| Host-provided data during bootstrap | Lets Python keep the rich model while S3 code focuses on rendering shape | Can hide missing language features and delay self-hosting constraints | Useful only as an interim bridge with clear replacement criteria |

These alternatives may support prototypes. They become brittle if they do not
preserve arity, type, ordering, and source-metadata invariants.

## Required future model

Conceptual target data shape:

```text
record AssemblyProgram {
  version
  functions
}

record AssemblyFunction {
  name
  return_type
  params
  registers
  body
}

record AssemblyInstruction {
  opcode
  operands
  source
}

enum AssemblyOperand {
  Register(name)
  Constant(value)
  Label(name)
  Function(name)
}
```

This is a design sketch, not current S3 syntax.

Required first:

- immutable record-like values with named fields;
- field construction and field access;
- arrays of structured values or an equivalent ordered collection model;
- a closed set of opcode/type tags, even if initially represented as numeric
  tags;
- a safe operand representation that prevents invalid field combinations;
- deterministic source-span representation.

Useful later:

- payload-carrying enums or sum types;
- pattern matching over enum cases;
- structural equality for records and arrays;
- modules for sharing renderer helper definitions.

Out of scope:

- arbitrary object identity;
- inheritance;
- dynamic maps;
- broad runtime reflection;
- replacing the Python Assembly model in this delivery.

## Relationship with strings and arrays

Strings and arrays remain separate prerequisites:

- Strings are necessary for names, labels, opcodes, comments, separators,
  newlines, and final Assembly text.
- Existing arrays can represent ordered collections such as functions,
  registers, labels, blocks, instructions, and operands.
- Existing arrays cannot be function parameters, return values, nested arrays,
  or first-class IR values.
- Records or structs are needed for program, function, block, instruction, and
  source-span shape.
- Enums or sum types are needed for opcodes, Assembly types, operand kinds, and
  optional payloads.
- Formatting helpers are still required to produce byte-for-byte deterministic
  output.

## Impact map

| Area | Current support | Future change needed | Risk | Notes |
| --- | --- | --- | --- | --- |
| Lexer | Tokens for functions, scalars, arrays, `match`, punctuation, and reserved string literals | Add record/enum keywords or punctuation only when syntax is chosen | Medium | Avoid conflicting with existing identifiers. |
| Parser | Parses scalar types, fixed arrays, calls, indexing, assignments, returns, and ternary `match` | Parse record/enum declarations, construction, field access, and possibly match arms | High | Parser diagnostics must stay deterministic. |
| AST | Models scalar expressions, calls, arrays, assignments, blocks, and functions | Add structured type, value, field, and variant nodes | High | AST serialization should remain stable. |
| Typechecker/semantic analysis | Validates scalars, arrays, function signatures, mutability, and ternary cases | Validate fields, constructors, enum tags, payloads, and structured equality rules | High | Invalid combinations must fail before lowering. |
| Lowering | Lowers arrays to memory and expressions to scalar IR | Lower structured values or reject unsupported uses explicitly | High | Layout and lifetime choices affect IR and runtime. |
| IR | Scalar value types plus memory objects and memory instructions | Represent structured data directly or via a documented lowering model | High | IR versioning may be affected if new value kinds are added. |
| Hosted emulator | Executes scalar and memory behavior | Execute any new structured representation or reject it with stable diagnostics | High | Runtime errors must match the semantic contract. |
| Native backend | Emits current validated Assembly and memory operations | Implement or explicitly reject structured runtime support | High | Data layout choices need a stable ABI direction. |
| Tests | Arrays, ternary `match`, diagnostics, Assembly, and tool checks | Add parser, semantic, lowering, runtime, and golden coverage for structured data | Medium | Keep fixtures small and deterministic. |
| Diagnostics | Structured Python diagnostics exist for compiler failures | Add focused diagnostics for malformed records/enums and invalid field access | Medium | Public diagnostic codes need intentional updates. |
| Docs | Existing self-hosting, array, string, and Assembly renderer contracts | Keep structured data contract aligned with actual implementation stages | Low | This document is an inventory, not a promise of immediate implementation. |

## Acceptance criteria for structured data support

Future structured data support is ready for partial self-hosting only when:

- record or struct syntax is defined;
- named fields are validated;
- structured values can be constructed;
- fields can be accessed deterministically;
- enum, sum type, or an equivalent variant model exists;
- pattern matching or safe tag dispatch exists for variants;
- arrays of structures or an equivalent ordered representation exists;
- tests and diagnostics are deterministic;
- the model can represent future `AssemblyInstruction` data without invalid
  opcode/operand combinations.

## Relevance for Assembly renderer subset

The future renderer needs at least:

- a list of functions;
- a list of registers;
- a list of labels or blocks;
- a list of instructions;
- one opcode per instruction;
- typed operands;
- textual names;
- deterministic ordering.

Dependency split:

| Renderer need | Depends on |
| --- | --- |
| Names, labels, opcode text, separators, final output | Strings and formatting helpers |
| Ordered functions, registers, blocks, instructions, operands | Arrays or equivalent ordered collections |
| Program/function/block/instruction/source-span shape | Records or structs |
| Opcode, type, and operand-kind choices | Enums, sum types, or safe tags |
| Byte-for-byte output | Formatting helpers and deterministic comparison |

Without records or enums, an `AssemblyInstruction` representation must rely on
positional arrays and numeric tags. That can demonstrate a narrow path, but it
cannot safely express which operands are valid for each opcode or which optional
payloads are present.

## Next recommendations

0.10-L:
Define an `AssemblyProgram` data contract using existing resources and the gaps
identified here.

0.10-M:
Decide the first real implementation target: minimal string type support or
minimal record/struct syntax.

0.10-N:
Create a Python-vs-S3 harness for the Assembly renderer subset, even if the S3
component starts as a stub or placeholder.

Do not treat these steps as immediate implementation commitments. They are the
smallest planning path from documented gaps toward a verifiable renderer
experiment.
