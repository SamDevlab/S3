# Generic Syntax, IR, and Verifier V1

This specification defines the representability increment after the ordinary
compiler substrate. It is a data-architecture contract, not a parser,
lowerer, emitter, or self-hosted compiler authorization.

## Boundary decision

The current semantic language rejects `vector<Composite>` as a field of another
aggregate. The implementation therefore does not change the public ABI or the
Assembly format. The S3 projection uses parallel `vector<i64>` fields and
direct IDs; composite records are not nested in arena storage.

```text
COMPOSITE_VECTOR_AS_AGGREGATE_FIELD=BLOCKED
SUPPORTING_LANGUAGE_EXTENSION_REQUIRED=NO
SUPPORTING_LANGUAGE_EXTENSION=NOT_REQUIRED_FLAT_PARALLEL_ARENAS
PUBLIC_ABI_CHANGED=NO
ASSEMBLY_FORMAT_CHANGED=NO
```

## SyntaxArena

`NodeId` is a direct integer allocated by `SyntaxArena`. A `SyntaxNode` stores
only:

- `kind` from the closed `NodeKind` domain;
- `SyntaxSpan(file_id, start, end)`;
- a discriminated `payload_kind` and payload-arena ID;
- `first_child` and `child_count` into one global child-ID arena.

Payloads are stored in kind-specific arenas for integer, float, text, symbol,
type, operator, declaration, and function payloads. The mapping from node kind
to payload kind is the sole payload authority. A node never owns child
objects. Child traversal is O(child count), and node lookup is O(1) by direct
ID.

The supported node domain covers the current AST families: literals,
identifiers, calls, record and generic type expressions, index/slice/field
access, unary/binary/match/len/address/dereference expressions, declarations,
blocks, control flow, functions, foreign functions, records, enums, modules,
imports, and a program root.

Validation is structural and parser-independent. It rejects invalid kinds,
spans, payload discriminants, payload IDs, child ranges, node references,
symbol/type references, and roots. It does not inspect source text.

Checkpoint/rollback captures the node, child, payload, and root cursors. Direct
IDs already committed are never renumbered; IDs allocated after rollback may
leave gaps.

## Generic IRProgram

The IR uses one authoritative arena for each entity:

```text
IRProgram
  FunctionArena
  BlockArena
  InstructionArena
  ValueArena
  ParameterArena
  MemoryObjectArena
  StaticStringArena
  result-type / operand / result / target sequence arenas
```

`IRFunction` stores ranges for parameters, result types, values, memory, and
blocks plus an entry `BlockId`. `IRBlock` stores its function owner, label
symbol, instruction range, and terminator ID. `IRInstruction` stores ranges
for zero, one, or many results, operands, and targets. The opcode and type
domains mirror `bootstrap/s3/ir.py`; no future opcode or speculative type is
introduced.

The model supports all current reference IR types and opcodes, reference and
slice metadata, static-string IDs, memory objects, calls, control-flow
terminators, and multi-result calls without a vector-only special path.

`IRBuilder` allocates identities directly. It never rescans source,
reconstructs IDs from instruction counts, or replays builder events.

## Transactions

An IR checkpoint is the tuple of all arena cursors. Builder checkpoints also
capture the open function/block metadata. Rollback restores those cursors and
metadata in O(number of arenas), while arena rollback removes only allocations
made after the checkpoint. No whole-program clone is used.

## Independent verifier

`IRVerifierKernel` consumes only `IRProgram` and `VerifierConfig`. It does not
accept or inspect AST, SyntaxArena, semantic state, lowerer state, fixture
names, or expected output. Temporary registries are external state and are
discarded after each call; the IR digest is checked before and after
verification.

The deterministic pass order is:

1. static-string collection;
2. function and identity collection;
3. per-function values, parameters, memory, and blocks;
4. definition and type checks;
5. opcode contracts and calls;
6. CFG edge construction and reachability;
7. iterative dominance;
8. use-dominance validation.

The verifier rejects duplicate identities/producers, unknown values and
targets, invalid memory, malformed block terminators, invalid opcode/type
contracts, call signature mismatches, invalid reference/slice metadata, and
return/multi-result mismatches. Unknown opcodes fail closed.

The result is structured with success, deterministic diagnostic code/message,
function/block/instruction IDs, and successful CFG/reachability/dominator
evidence. A first error is selected by arena/function/block/instruction order,
never by host hash order.

## Determinism and complexity

All identity and sequence arenas are traversed by direct numeric ID order.
Capability entries are frozen in lexical name order; composite vector builtin
signatures use the existing encoded signature authority. Structural digests
use canonical JSON with sorted keys.

Expected work is O(1) node/value/instruction append and lookup, O(children) or
O(operands) range traversal, O(functions) registration, O(instructions + CFG
edges) CFG construction, and O(B²) worst-case for the bounded iterative
dominance calculation. No pass reparses source, scans AST, clones the whole
program, or rebuilds layouts per instruction.

## Non-goals

This contract does not add a lexer, parser, semantic analyzer, generic
lowering, optimizer, emitter, `compile_program`, self-compilation, Stage2, a
new public ABI, or a versioned Assembly format. Gate 3/4 remain partial and
Gate 15 remains explicitly unauthorized.
