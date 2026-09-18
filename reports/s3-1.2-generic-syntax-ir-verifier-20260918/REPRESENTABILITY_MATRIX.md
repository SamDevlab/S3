# Generic Syntax and IR Representability Matrix

| Structure | Representation | Status | Evidence boundary |
| --- | --- | --- | --- |
| SourceView / Cursor | existing substrate IDs and bounded views | PASS | inherited from PR #298 |
| Token | fixed scalar shape / future arena input | PARTIAL | no lexer in this increment |
| SyntaxArena | direct NodeId arena plus child-ID range arena | PASS_HOSTED | structural validator and digest |
| Syntax payloads | kind-specific fixed payload arenas | PASS_HOSTED | payload authority negatives |
| ScopeArena | existing direct-ID arena | PASS | inherited |
| DeclarationArena | existing direct-ID arena | PASS | inherited |
| TypeArena | stable IDs referenced by syntax/IR | PARTIAL | metadata remains future work |
| Function identity | direct IR function IDs plus symbol IDs | PASS_HOSTED | duplicate identity rejection |
| Storage / memory | direct memory-object arena | PASS_HOSTED | type/length/mutability checks |
| IRProgram | parallel entity and sequence arenas | PASS_HOSTED | generic builder |
| Function IR | range-owned parameters/values/memory/blocks | PASS_HOSTED | function registry |
| BlockArena | function-owned direct BlockId | PASS_HOSTED | CFG and terminator checks |
| InstructionArena | direct InstructionId and scalar ranges | PASS_HOSTED | opcode contracts |
| ValueArena | direct ValueId with type/owner metadata | PASS_HOSTED | definitions/use-dominance |
| StaticStringArena | direct IDs in deterministic order | PASS_HOSTED | ordering verifier |
| Verifier state | external per-run registries and CFG sets | PASS_HOSTED | digest unchanged |
| Emitter/output state | existing OutputSink only | PARTIAL | emitter intentionally absent |
| Whole-program compiler context | data composition, no phase orchestration | PARTIAL | no compile_program |

## Language boundary

`vector<Composite>` as an aggregate field was tested directly and remains
blocked by the current semantic contract. The model avoids that limitation
without changing ABI or Assembly by using parallel scalar vectors in the S3
projection. No second layout engine or nested-container extension was added.

## IR operation coverage

| Reference family | Generic IR authority | Verifier rule |
| --- | --- | --- |
| constants / static strings | `CONST`, `CONST_STR` | PASS |
| moves / unary / arithmetic | `MOVE`, `INVERT`, arithmetic opcodes | PASS |
| numeric relation / compare | `RELATE`, `COMPARE` | PASS |
| conversion | `CONVERT` | PASS |
| calls / dynamic builtins | function IDs and deterministic capability table | PASS |
| scalar memory | `LOAD`, `STORE`, `ADDRESS_OF` | PASS |
| references / slices | reference and slice metadata | PASS |
| multi-cell calls/results | result ranges of width 0/1/N | PASS |
| control flow | `RETURN`, `JUMP`, `BRANCH3` | PASS |

This table records representability and verification, not lowering or source
execution. Gate 7 remains bounded to the represented reference IR domain until
generic syntax, semantic passes, and lowering are added.

## Complexity

- node/value/instruction allocation and lookup: O(1);
- child/operand/result/target traversal: O(range length);
- function/block/value collection: O(arena entries);
- CFG construction/reachability: O(blocks + edges);
- dominance: deterministic bounded iterative O(B²) worst case;
- verification uses no source rescans, AST traversal, IR reparsing, or whole
  program copies.
