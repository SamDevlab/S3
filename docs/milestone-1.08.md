# Milestone 1.08 - Multi-Cell Result Architecture and Formats

Status: In progress - architecture decision accepted in Draft PR #127

Milestone 1.08 defines the compiler format and execution architecture for
functions that return one fixed-layout source value with multiple scalar cells.

The accepted decision is [ADR-0022](decisions/ADR-0022-aggregate-function-results.md).

## Decision Summary

S3 will represent aggregate function results as ordered result cell lists in IR
and S3 Assembly. The source language still has one return expression and one
declared return type. There are no tuple returns, variadic returns, public
pointers, heap objects, exceptions, or generic result types.

The selected architecture is:

- result width and cell types come from `FixedValueLayout`;
- IR functions carry ordered result cell types;
- IR `CALL` defines an ordered result register group;
- IR `RETURN` consumes an ordered result operand group;
- S3 Assembly represents function result type lists, `TCALL` destination lists,
  and `TRET` source lists;
- width 1 preserves the existing native `rax` path;
- width greater than 1 uses a hidden native sret area internal to the x86-64
  backend.

## Format Impact

IR JSON and S3 Assembly require a coherent version bump to `0.6.0` once the
implementation lands. Version `0.5.0` remains a legacy width-1 format and must
continue to be accepted when valid.

No source syntax version bump is required because no source grammar is added.

## Implementation Work

Remaining 1.08 implementation units:

- add IR result cell groups;
- add Assembly result cell lists;
- update serializers, parsers, renderers, and legacy readers;
- update verifier checks;
- preserve groups through optimizer and SSA;
- execute multi-cell returns in the emulator;
- implement hidden sret in the x86-64 backend.

## Non-Goals

- No source tuple return syntax.
- No public pointer type.
- No heap allocation.
- No C ABI compatibility claim.
- No aggregate source semantics beyond one fixed-layout return value.
