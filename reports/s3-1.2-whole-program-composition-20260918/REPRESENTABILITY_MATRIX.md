# Whole-Program Composition Representability Matrix

| Structure | Status | Evidence |
|---|---|---|
| SourceBundle / SyntaxArena | REPRESENTABLE_NOW | Existing substrate and prepared-artifact validation |
| ProgramRegistry | REPRESENTABLE_NOW | `bootstrap/s3/whole_program.py`, deterministic registration tests |
| ModuleTable / FunctionTable | REPRESENTABLE_NOW | Direct IDs, explicit ranges, duplicate rejection |
| NominalTypeTable | REPRESENTABLE_NOW | Nominal module + declaration identity |
| TypeArena | REPRESENTABLE_NOW | Primitive, structural, nominal, parametric and transactional tests |
| ScopeArena / DeclarationArena | REPRESENTABLE_NOW | SemanticState direct-ID associations |
| Storage / call / mutability associations | REPRESENTABLE_NOW | Explicit SemanticState maps and validation |
| DiagnosticArena | REPRESENTABLE_NOW | Bounded direct-ID structured diagnostics |
| PhaseState / transactions | REPRESENTABLE_NOW | PhaseOrchestrator and failure suppression tests |
| IRProgram / verifier | REPRESENTABLE_NOW | PR #299 generic verifier integration |
| OutputSink / CompileResult | REPRESENTABLE_NOW | Caller-owned output transaction and result digest |
| WholeProgramContext | REPRESENTABLE_NOW | Prepared control-plane composition harness |
| Lexer / parser | BLOCKED_BY_SCOPE | Outside this increment; no fake implementation |
| Generic lowering | BLOCKED_BY_SCOPE | Explicitly skipped for TEST_ARTIFACT_INPUT |
| Emitter | BLOCKED_BY_SCOPE | Explicitly skipped; prepared bytes only |
| Source-to-output compile_program | BLOCKED_BY_SCOPE | Root fails closed without prepared artifacts |
| Stage1 V4 / Stage2 / Stage3 | NOT_AUTHORIZED | Project policy remains unchanged |

`vector<Composite>` as an aggregate field remains blocked. The implementation
uses flat arenas, direct IDs, and explicit ranges rather than expanding the
language representation.
