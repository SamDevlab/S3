# Milestone 2.83: Call and Aggregate Lowering

M2.83 defines a bounded call-lowering plan with explicit ordered arguments
and ordered result cells. The plan is an experimental producer for the
self-hosting train and does not replace production call lowering.

## Contract

- calls have a stable callee identity;
- argument types and argument registers are paired in declared order;
- zero, scalar and aggregate result lists are represented explicitly;
- result registers are assigned after the argument register window;
- the S3 candidate validates the bounded shape and computes the same
  deterministic plan identity as the Python reference.

## Non-claims

M2.83 does not change public IR JSON, the production `CALL` instruction,
verifier behavior, native ABI behavior, candidate default selection,
performance claims or global T4. Composed IR closure is later work.
