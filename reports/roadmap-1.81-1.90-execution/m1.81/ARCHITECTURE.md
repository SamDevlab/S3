# M1.81 Native Async IR and Resumable Frames

## Problem

M1.71 introduced source-visible `async fn`/`await` and a deterministic suspension plan, but ordinary execution still followed the conventional synchronous IR. M1.81 makes resumable async IR an executable compiler path rather than side metadata.

## Public surface

`AsyncIRProgram`, `AsyncIRFunction`, `AsyncIRFrame`, `AsyncIRSlot`, `AsyncIRBlock`, `AsyncIROp`, `execute_async_ir`, and `execute_async_program` are compiler/runtime contracts. `CompilationResult.async_ir` carries the executable async program.

## Lowering and execution

The async language preprocessor removes only contextual `async`/`await` syntax before delegating core parsing, while retaining exact compiler metadata. Executable actions are lowered into deterministic frame slots and explicit running/suspended/terminal states. For an async entry, `pipeline.run_source()` now routes through `execute_async_program`; it does not execute the conventional direct-call result as the normative async path.

Each await produces a real suspension boundary. The first poll reaches `suspended_N`; a later poll resolves the owned awaited Future/callee, stores the result if required, and resumes at `running_N+1`. Completion, failure, cancellation, poll budget, and terminal consumption are explicit.

## Ownership and borrow model

Each frame value has one owner. `Future<T>` ownership is handled by M1.82. Ordinary references/slices remain forbidden across await and PR182's fail-closed borrow rule is revalidated before async lowering. Terminal cleanup drops live, non-moved owned Future values once; moved/consumed values are not dropped again.

## Boundedness and determinism

Async polls are capped at `100000`. Frame slot order, action order, suspension numbering, block names, compiler metadata, and serialized async IR are deterministic. Unsupported suspension inside control-flow is rejected in V1 rather than silently falling back to synchronous execution.

## Platform model

Hosted execution is the certification path available on this campaign host. Platform-native async-frame execution remains a separate target certificate and is not inferred from hosted execution.
