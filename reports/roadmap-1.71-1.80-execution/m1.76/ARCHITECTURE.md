# M1.76 - Bounded Async Channels And Select V1 Architecture

## MILESTONE

`M1.76 BOUNDED_ASYNC_CHANNELS_AND_SELECT_V1`

## PROBLEM

Structured tasks need message passing without hidden shared mutation or an
unbounded queue.

## PUBLIC_SURFACE

`AsyncChannel`, `Sender`, `Receiver`, `OwnedMessage`, and awaitable send/recv
operations are bounded. `select` accepts a finite tuple of receivers and
returns the first ready entry by registration index.

## OWNERSHIP_MODEL

Successful send consumes the caller's `OwnedMessage` and stores its payload in
the channel. Failed send returns recoverable ownership through the operation.
Receive creates a new owned message. Sender/receiver closure is idempotent.

## RESOURCE_MODEL

Capacity is fixed at construction and applies to queued messages. A closed
channel drains already committed messages, then reports closed. There is no
unbounded fallback queue.

## FAILURE_MODEL

Full, empty, closed, invalid ownership, and duplicate close are explicit
`ChannelError` outcomes. Select over no ready operation returns a pending result
and never spins.

## LOWERING_MODEL

Awaitable send/recv operations are M1.71 futures. A full channel or empty
receiver yields pending; a producer/consumer wake is an explicit later poll or
executor wake, not an implicit thread.

## DETERMINISM_MODEL

Queue order is FIFO. Select tie-breaking is the smallest registration index;
channel readiness cannot depend on hash or host scheduling order.

## PLATFORM_MODEL

Hosted, cooperative, single-threaded semantics. Cross-thread transport and
lock-free claims are out of scope.

## OUT_OF_SCOPE

Unbounded channels, async streams, actor frameworks, implicit cloning, and
multi-thread task migration.

## TEST_STRATEGY

Focused tests cover capacity/backpressure, FIFO, ownership recovery, close and
drain semantics, awaitable send/recv, deterministic select ties, and bounded
no-ready behavior.
