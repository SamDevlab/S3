# M1.39 Architecture Decision Draft

## Decision state

```text
STATUS=BLOCKED_ARCHITECTURE_DECISION
MILESTONE=1.39
IMPLEMENTATION_AUTHORIZED_BY_ROADMAP=NOT_YET
```

This draft records the decisions that must be made before implementation. It
does not choose them and does not alter the normative specification.

## Required decisions

### Representation

Choose whether `OwnedByteBuffer`, dynamic text, and borrowed views are distinct
source types, opaque handles, or one closed value family. Define which values
can cross function/module boundaries and whether a view remains valid after
owner growth or mutation.

### Allocation and limits

Define the allocation provider, initial capacity, growth rule, maximum length,
overflow behavior, allocation failure, and whether allocation is deterministic
under hosted and native execution. State whether an arena is part of M1.39 or
is deferred.

### Ownership and aliasing

Define copy, move, borrow, mutable borrow if any, aliasing, lifetime boundaries,
slice invalidation, close/free behavior, and diagnostics. The contract must not
silently introduce raw pointers or a partial borrow checker.

### Syntax and typing

Define declarations, constructors, text literals versus runtime values, view
types, append/concat/slice/search typing, conversion rules, and how invalid
operations are rejected. State whether the first API is source-level or a
host/provider-only boundary.

### Failure model

M1.39 needs an observable result for invalid UTF-8, parse failure, overflow, and
capacity failure. Decide whether M1.39 uses a narrowly specified temporary
status contract or whether the M1.42 error milestone must move earlier. Do not
invent implicit exceptions or sentinel values.

### IR, Assembly, and native ABI

Define the minimum IR/Assembly operations, hosted representation, native x86-64
layout, alignment, return/parameter convention, and C/foreign boundary. The
existing scalar ABI and static-string `.rodata` path do not answer these dynamic
questions.

### Test and determinism contract

Define allocation-failure injection, stable serialization, O0/O1 observable
equivalence, differential oracle shape, and native cleanup/leak evidence.

## Required resolution artifact

Before implementation, a reviewed ADR/spec amendment must resolve every item
above and update the M1.39 roadmap contract or explicitly narrow M1.39 to a
host/provider-only preparation milestone. Only then can the implementation
phase resume.
