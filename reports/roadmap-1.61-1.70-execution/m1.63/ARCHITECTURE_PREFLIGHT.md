# M1.63 Architecture Preflight

## Findings

- S3 source already has a compiler-known `range` AST and lowering path with
  explicit start, end, and step expressions.
- Dynamic vectors already snapshot iteration, while maps and sets preserve
  insertion order but had no public Python iteration protocol.
- A general iterator object or trait would introduce a new ownership/lifetime
  surface that is not required for deterministic V1 iteration.

## Decision

Add a small checked `I64Range` value and closed `__iter__` protocols over the
existing dynamic collection/view classes. Map iteration is an ordered pair
sequence; set iteration is an ordered value sequence. Source collection-for
syntax and consuming iteration remain explicitly deferred.

## Gate

Use T0, direct range/collection tests at T1, the range/loop/collection
subsystem at T2, and an IR/native/ownership iteration shard at T3.
