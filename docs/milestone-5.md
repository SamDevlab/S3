# Milestone 5: Memory GVN for immutable loads

## Scope

GVN may reuse a repeated `LOAD` only when its memory object is registered as
immutable. Mutable memory and unregistered memory remain excluded.

## Safety contract

An immutable memory object cannot be changed after initialization. The existing
dominance-based GVN proof therefore applies to repeated loads with the same
index, memory object, and result type. This milestone does not add alias
analysis, Memory SSA, or mutable-memory reasoning.

## Acceptance

- repeated loads from immutable memory are folded;
- repeated loads from mutable memory remain unchanged;
- unknown memory objects remain unchanged;
- SSA verification, differential tests, and O0/O1 equivalence remain valid.
