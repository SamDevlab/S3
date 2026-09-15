# Self-hosting architecture lessons

These rules are project-level lessons from the self-host research line. They are
independent of any single prototype generation.

## 1. Self-hosting is not the language

A failed or deferred self-host implementation does not invalidate S3. The
language specification, Python reference compiler, IR, verifier, emulator,
native backend, and normal roadmap remain independently useful and testable.

## 2. Canonical qualification is confirmation, not discovery

Large canonical runs must not be used as the normal debugging loop. Local,
bounded, focused, and differential evidence should close ordinary defects
before a canonical qualification is considered.

## 3. Generic architecture must precede broad self-source coverage

A future compiler must have one generic pipeline before claiming broad
self-source progress:

```text
source
  -> lexer
  -> parser
  -> generic AST/HIR
  -> semantic passes
  -> generic IR
  -> verifier
  -> emitter
  -> compile_program
```

Broad source coverage without this composition root is not self-hosting.

## 4. Vertical slices are acceptance tests, not production architecture

End-to-end slices are valuable because they expose integration defects early.
Production code, however, must not dispatch by slice, milestone, fixture, source
name, known cursor, ValueId, or InstructionId. Slice fixtures should become
regression tests for generic compiler behavior.

## 5. Semantic identity is explicit

Scope and declaration identity must be represented directly. Type, value,
storage, and mutability resolution for one use must resolve to the same
`DeclarationId` where applicable. Ordinary lookup must not repeatedly rescan a
function prefix.

## 6. IDs are allocated, never reconstructed

`FunctionId`, `DeclarationId`, `StorageId`, `BlockId`, `ValueId`, and
`InstructionId` should come from deterministic allocators/arenas. Recounting
source text to reconstruct IDs is prohibited architecture.

## 7. Speculative lowering is transactional

Probe/non-owner lowering must commit no state. Generic lowering should support
checkpoint, commit, and rollback over allocator/arena state. Every syntax
subtree has one committed lowering owner.

## 8. IR completeness is planned before frontend breadth

A self-host compiler must map every required Stage1 language operation to a
generic IR operation before broad frontend completeness is claimed. The IR
must be self-host representable, deterministic, and independently verifiable.

## 9. The verifier is first-class

The verifier must reject duplicate IDs/producers, invalid references, invalid
storage or blocks, malformed terminators, fallthrough after terminators, and
invalid aggregate/call metadata without relying on parser correctness.

## 10. Emission is part of feature completeness

A language feature is not complete for self-hosting if it stops at parser,
semantics, or IR. The emitter and real output transport are part of the same
contract. Unknown IR must fail closed rather than be skipped or replaced by
placeholder output.

## 11. Transport must be semantically transparent

Source and output may be bounded or streamed, but chunk boundaries, LF/CRLF,
manifest ordering, and buffer segmentation must not change semantics. A host
harness may transport opaque bytes; it must not perform hidden lexing, parsing,
resolution, lowering, or emission during a true self-host proof.

## 12. Bootstrap stages must be named before implementation

A future effort must distinguish Stage0 reference compilation, Stage1 compiler
execution, self-compilation output, and Stage2 execution before any bootstrap
claim is made. Producing a next-stage artifact and executing it are separate
gates.

## 13. Complexity is an architectural invariant

The compiler architecture must avoid:

- repeated function-prefix scans for local lookup;
- source recounting for IDs;
- whole-program reparsing per function;
- rebuilding aggregate layouts per use;
- pathological compiler-state or output copying;
- hidden resource budgets that merely mask an unsuitable algorithm.

Scaling tests should be introduced with the subsystem, not after full compiler
integration.

## 14. Host/reference code is an oracle, not hidden self-host machinery

Python may remain the reference implementation, provide Stage0, and serve as a
differential oracle. A true self-host proof must disable semantic host compiler
entry points and allow the host only mechanical transport, invocation, output
capture, hashing, and resource control.

## 15. Preserve failed research

Rejected prototypes, minimal reproducers, reports, and regression cases are
valuable engineering evidence. They should be frozen rather than erased or
silently rewritten into successful history.
