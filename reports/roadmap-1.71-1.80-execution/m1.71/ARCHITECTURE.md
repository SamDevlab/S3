# M1.71 - Async/Await Core V1 Architecture (PR #182 corrected)

## MILESTONE

`M1.71 ASYNC_AWAIT_CORE_V1`

## PROBLEM

S3 needs source-visible `async fn` / `await` syntax, compiler-owned suspension metadata, and a hosted state-machine contract that preserves move-only ownership without allowing ordinary lexical references to survive suspension.

## PUBLIC SURFACE

Source syntax V1 accepts:

- `async fn name(...) -> T:`
- `await direct_async_call(...)`

`CompilationResult` exposes an `AsyncSyntaxTree` and deterministic `AsyncStateMachinePlan` values. The hosted runtime remains `AsyncFuture`, `AsyncFrame`, `Poll`, and owned frame slots.

## FRONT-END / PARSER MODEL

`async_frontend.parse_async_source()` is the bounded M1.71 parser extension. The existing recursive-descent parser remains the core grammar parser.

The extension first lexes the original source, recognizes contextual `async` / `await` markers outside comments and string literals, removes only the marker prefixes before delegation to the core parser, and deterministically maps the transformed parser offsets back to the original async marker/call locations. Removing the prefixes rather than replacing a top-level `async` marker with spaces avoids producing a false indentation token at column 1.

The core AST therefore keeps its existing ABI and transformed parser offsets; the async side tree keeps the original source locations plus the mapped parser offsets used to bind async markers to parsed functions/direct calls. No global lexer keyword change is required.

## SEMANTIC MODEL

The async semantic pass runs before the existing core semantic analyzer and fails closed unless:

- `await` appears inside an `async fn`;
- the awaited expression is a direct call to a declared async function;
- every async function call in V1 is immediately awaited;
- no ordinary lexical reference or slice binding is live at the await point;
- the async function is non-generic in V1.

The immediate-await restriction is intentional. M1.71 does not introduce a general public `Future<T>` storage type, reference counting, or lifetime annotations.

## OWNERSHIP MODEL

Hosted suspended values live in `AsyncFrame` owned slots. Slots move at most once and drop at most once. Completion, failure, cancellation, and abandonment deterministically drop initialized non-moved slots.

A live hosted `BorrowToken` rejects suspension. The source semantic pass additionally rejects ordinary reference/slice bindings live at an `await` point.

## RE-ENTRANCY

A future already in `RUNNING` rejects another `poll()` and rejects re-entrant cancellation. This prevents simultaneous/re-entrant entry into the same hosted state machine.

## LOWERING MODEL

For each source-level async function the compiler emits a deterministic `AsyncStateMachinePlan` containing:

- frame-slot identities derived from parameters/locals;
- await points in stable source order;
- explicit suspended/resume state names;
- terminal `completed`, `failed`, and `cancelled` states.

For M1.71 V1, an immediately-awaited call still uses the existing direct call IR for hosted execution while the compiler retains the explicit suspension plan as async lowering metadata. This closes the previously missing source/parser/semantic/lowering integration, but it does **not** claim native resumable-frame IR/backend execution. Materializing resumable frames as first-class IR/backend state is reserved for M1.81.

## RESOURCE MODEL

Hosted frames have a finite slot limit. Source suspension points and compiler plans are finite and deterministic. No worker thread, unbounded queue, GC, or reference-counting runtime is introduced.

## FAILURE MODEL

Invalid await scope/target, un-awaited async calls, live references across await, re-entrant polling, double terminal consumption, and frame overflow fail closed through explicit diagnostics/results.

## DETERMINISM MODEL

Original async marker/call locations are retained explicitly while parser offsets are mapped deterministically after contextual-prefix removal. Async functions and await points are emitted in declaration/source order. State names and frame-slot identities are deterministic.

## PLATFORM MODEL

The source/compiler surface and hosted state machine are platform-neutral. Native resumable execution certification is not claimed by M1.71.

## OUT OF SCOPE

Stored/general Future values, generic async functions, multi-file async rewriting, async traits, async streams, generators, multi-thread task migration, native resumable-frame IR/backend code generation, and work stealing.

## TEST STRATEGY

Focused PR #182 correction tests cover source `async fn` / `await` compilation, deterministic suspension plans, await scope/target diagnostics, ordinary-reference rejection across await, re-entrant poll rejection, and hosted immediate-await execution. Existing M1.71 hosted ownership/drop tests remain applicable.
