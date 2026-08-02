# Milestone 1.08 - Multi-Cell Result Architecture and Formats

Status: Implementation complete locally in Draft PR #127; user validation pending

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

IR JSON and S3 Assembly writers emit `0.6.0`. Version `0.5.0` remains a legacy
width-1 format and continues to be accepted when valid.

No source syntax version bump is required because no source grammar is added.

## Implementation Work

Implemented 1.08 units:

- IR result cell groups;
- Assembly result cell lists;
- serializers, parsers, renderers, and legacy readers;
- verifier checks for result width and type agreement;
- optimizer and SSA preservation of result groups;
- emulator execution of multi-cell returns and full-group discard;
- hidden sret in the x86-64 backend for width greater than 1;
- scalar-only native entry point.

Coverage has been added across formats, verifier, SSA, optimizer, emulator,
aggregate language returns, and native ABI surfaces. Tests authored after the
no-agent-testing policy change are pending user validation.

## Non-Goals

- No source tuple return syntax.
- No public pointer type.
- No heap allocation.
- No C ABI compatibility claim.
- No aggregate source semantics beyond one fixed-layout return value.
