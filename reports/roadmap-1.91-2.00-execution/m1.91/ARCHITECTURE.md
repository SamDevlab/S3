# M1.91 Architecture: Async Select

## Scope

M1.91 adds a first-class `select:` statement to the V0.6 source surface. A
select arm is `case <awaited async call or owned Future>:` followed by a
bounded statement block.

## Lowering

The parser produces `ast.SelectStatement` and `ast.SelectArm` nodes. The
semantic analyzer validates every operation and joins ownership state across
arms. The async language lowerer emits one `AsyncActionKind.SELECT` with
explicit `AsyncSelectArm` records. Each arm contains its operation and its
lowered body actions, so nested suspension remains visible to executable IR.

`lower_executable_async_ir` counts nested select suspension points when it
materializes frame states. `AsyncIRFrameRuntime` expands the selected arm into
its action queue only after the select suspension resumes; ordinary source
order and the existing frame poll protocol remain authoritative.

## Determinism and ownership

- Candidate arms are visited in source order.
- Select arity is bounded by `MAX_SELECT_ARITY = 8`.
- Nested select depth is bounded by `MAX_SELECT_DEPTH = 8`.
- An owned Future used as an arm operation is consumed by the select decision.
- Unselected Future candidates are dropped during resolution or cancellation.
- A second await of a consumed Future is rejected during lowering.
- No detached task, generator, or implicit polling loop is introduced.

The hosted channel `select` helper shares the arity bound and retains its
lowest-index-ready behavior. The ordinary compiler IR receives a first-arm
materialization projection only so `CompilationResult` remains available; an
async source is executed exclusively through `async_ir`.
