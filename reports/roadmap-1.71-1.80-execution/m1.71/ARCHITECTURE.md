# M1.71 - Async/Await Core V1 Architecture (Corrected for PR #182)

## MILESTONE

`M1.71 ASYNC_AWAIT_CORE_V1`

## PROBLEM

S3 needs source-visible `async fn` / `await` syntax, compiler-owned suspension metadata, and a hosted state-machine contract that preserves move-only ownership without allowing ordinary lexical references to survive suspension.

## PUBLIC SURFACE

Source syntax V1 accepts:

- `async fn name(...) -> T:`
- `await direct_async_call(...)`

`CompilationResult` exposes the parsed async syntax side tree and deterministic `AsyncStateMachinePlan` values. The hosted runtime surface remains `AsyncFuture`, `AsyncFrame`, `Poll`, and owned frame slots.

## FRONT-END / PARSER MODEL

`async_frontend.parse_async_source()` is the M1.71 parser extension. The existing recursive-descent parser remains the core grammar parser. The extension lexes the original source, recognizes contextual `async` / `await` markers outside strings/comments, replaces only the marker spans with whitespace so every source offset remains stable, delegates the resulting grammar to the core parser, then binds the source markers back to parsed functions and direct call expressions.

This keeps the existing AST ABI stable while still giving the compiler a first-class `AsyncSyntaxTree` with exact source locations. `async` and `await` are reserved in the M1.71 source surface.

## SEMANTIC MODEL

The async semantic pass runs before the existing core semantic analyzer and enforces:

- `await` only inside an `async fn`;
- an async function call must be immediately awaited;
- the awaited target must be an async function;
- ordinary lexical reference/slice bindings may not be live at an await point;
- generic async functions are deferred in V1;
- arbitrary/stored Future expressions are deferred in V1.

The immediate-await restriction is intentional: M1.71 does not introduce a general public Future type, reference counting, or new lifetime syntax.

## OWNERSHIP MODEL

Hosted suspended values live in `AsyncFrame` owned slots. Slots move at most once and drop at most once. Completion, failure, cancellation, and abandonment deterministically drop initialized non-moved slots.

A live hosted `BorrowToken` rejects suspension. The source semantic pass additionally rejects ordinary reference/slice bindings live at an `await` point.

## RE-ENTRANCY

A future in `RUNNING` state rejects another `poll()` and rejects re-entrant cancellation. This prevents simultaneous/re-entrant entry into the same state machine.

## LOWERING MODEL

For each source-level async function the compiler emits a deterministic `AsyncStateMachinePlan` containing:

- frame slots derived from parameters/locals;
- await points in stable source order;
- explicit suspended/resume state names;
- terminal `completed`, `failed`, and `cancelled` states.

The hosted execution path currently lowers an immediately-awaited call through the existing direct call IR while retaining the explicit suspension plan as compiler metadata. This is intentionally narrower than a native resumable-frame IR/backend implementation; native resumable state-machine code generation is not claimed by M1.71 V1.

## RESOURCE MODEL

Hosted frames have a finite slot limit. Source suspension points and compiler plans are finite and deterministic. No worker thread, unbounded queue, GC, or reference-counting runtime is introduced.

## FAILURE MODEL

Invalid await scope/target, un-awaited async calls, live references across await, re-entrant polling, double terminal consumption, and frame overflow fail closed through explicit diagnostics/results.

## DETERMINISM MODEL

Source offsets are preserved through the parser extension. Async functions and await points are emitted in declaration/source order. State names and frame-slot identities are deterministic.

## PLATFORM MODEL

The M1.71 source/compiler surface and hosted state machine are platform-neutral. Native resumable execution certification is not claimed here.

## OUT OF SCOPE

Stored/general Future values, generic async functions, multi-file async rewriting, async traits, async streams, generators, multi-thread task migration, native resumable-frame code generation, and work stealing.

## TEST STRATEGY

Focused PR #182 correction tests cover source `async fn` / `await` compilation, deterministic suspension plans, await scope/target diagnostics, ordinary-reference rejection across await, re-entrant poll rejection, and hosted end-to-end immediate-ready execution. Existing M1.71 hosted ownership/drop tests remain applicable.
