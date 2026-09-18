# Phase Transaction Matrix

| Phase | Input | Commit effect | Failure rollback | Next legal state |
|---|---|---|---|---|
| INPUT | SourceBundle | session root accepted | no published artifacts | SYNTAX |
| SYNTAX | prepared SyntaxArena | syntax identity accepted | syntax artifacts remain caller-owned | REGISTRATION |
| REGISTRATION | ModuleSpec tuples | module/function/type/import/export IDs | all new registry tables rolled back | TYPE |
| TYPE | TypeSpec tuples | canonical TypeIds | post-checkpoint types removed; prior IDs survive | SEMANTIC |
| SEMANTIC | explicit seed associations | scopes/declarations/calls/types/storage | change log and arenas rolled back | LOWERING |
| LOWERING | none in V1 | SKIPPED marker only | no mutation | VERIFICATION |
| VERIFICATION | prepared IRProgram | verifier success recorded | IR is unchanged; diagnostic published | EMITTER |
| EMITTER | none in V1 | SKIPPED marker only | no mutation | OUTPUT |
| OUTPUT | prepared bytes | sink append committed | sink returns to phase checkpoint | FINALIZE |
| FINALIZE | committed state | deterministic result digest | terminal failure only | terminal |

The first fatal phase diagnostic is preserved. Dependent phases are marked
`SKIPPED`; a later phase cannot run after failure.
