# Milestone 1.03 - Acyclic Nested Records and Deterministic Composite Layout

Status: Complete

Milestone 1.03 extends the 1.00 and 1.02 record contracts to allow acyclic
nested record fields. It preserves the existing public IR, S3 Assembly,
diagnostic schema, native ABI, CLI, golden artifacts, baselines, tags, releases,
and package version.

## Completed Scope

- architectural audit of AST, parser, semantic analysis, module rewriting,
  lowering, IR, verifier, SSA/optimizer, emulator, native backend, and record
  tests;
- architecture gate confirming that non-return nested record values fit the
  current scalar IR and Assembly model;
- [ADR-0020](decisions/ADR-0020-acyclic-nested-record-layout.md);
- semantic layout graph and deterministic recursive-layout rejection;
- local nested records with two, three, and four record levels;
- imported records as fields;
- multi-module A/B/C nested record composition;
- qualified record constructors and nested qualified constructors;
- named initializers independent of declaration order;
- nonalphabetic field declaration order preserved by layout;
- member chains through nested fields;
- value copies, branches, loops, and nested parameters;
- `trit`, `tryte`, and no-payload enum scalar leaves;
- single-leaf nested record returns through the existing scalar return path;
- O0/O1 emulator coverage;
- Linux x86-64 native harness coverage for ELF O0/O1 when available.

## Canonical Layout Contract

`SemanticModel.record_leaves()` is the canonical source for nested record
layout. It defines:

- scalar leaf paths;
- scalar leaf types;
- depth-first traversal;
- declaration-order traversal at every record level;
- parameter scalarization;
- copies;
- member access;
- return classification.

`record_leaf_count()` is derived from the same model and is used only as a
counting/query operation. Implementations must not add a second independent
flattening algorithm for lowering, optimization, native code generation, or
tests.

The logical layout has no public offsets, alignment, padding, object header,
hidden pointer, physical aggregate metadata, or nominal alignment rule. It is a
deterministic scalar leaf list used before public IR and Assembly are emitted.

## Supported Forms

Nested records are supported in:

- literals and nested literals;
- qualified constructors such as `model.Outer(...)`;
- imported record fields;
- immutable locals;
- copies by value;
- function parameters;
- chained member access;
- branch, loop, and match contexts whose observable result is scalar;
- multi-file compilation with deterministic source-order independence.

At the 1.03 boundary, fields may be `trit`, `tryte`, no-payload enum types, or
acyclic record types. Arrays, recursive layouts, and arrays of records remain
rejected. `string` fields are covered by the later Milestone 1.04 fixed-text
contract.

## Return Contract

The public return convention remains scalar:

- IR: one `RETURN` operand;
- S3 Assembly: one `TRET` operand;
- native x86-64: one result through `rax`.

A record, including a nested record, may be returned only when it contains
exactly one scalar leaf. Multi-leaf record returns are rejected before backend
code generation. Milestone 1.03 does not introduce hidden return pointers,
multi-register returns, stack return areas, aggregate return opcodes, implicit
packing, or truncation to the first leaf.

## Diagnostics and Rejections

The compiler rejects before lowering:

- direct self-recursive record layouts;
- indirect local layout cycles;
- cross-module layout cycles;
- private nested types imported from another module;
- missing nested types;
- nominal mismatches, including same-name/same-shape types from different
  modules;
- missing or extra fields in nested constructors;
- invalid member chains;
- arrays of records;
- string fields at the 1.03 boundary, before the Milestone 1.04 fixed-text
  extension;
- multi-leaf record returns.

## Validation

Local focused validation for the final 1.03 checkpoint covered:

- nested record composition integration;
- recursive composite layout rejection;
- record composition contracts;
- native x86-64 integration harness collection;
- instruction-limit tests that share the native CI job;
- compileall;
- golden inspect;
- Assembly renderer comparison;
- whitespace checking.

On Windows hosts, ELF execution tests are collected and skipped by the native
toolchain fixture. Emulator O0/O1 and semantic pre-backend tests still execute
locally. On Linux x86-64 CI, the same native tests build and run ELF O0/O1.

## Explicitly Unsupported

- recursive record layouts;
- arrays as record fields;
- strings as record fields before the Milestone 1.04 fixed-text extension;
- arrays of records;
- aggregate returns;
- hidden return pointers;
- multi-register returns;
- heap allocation;
- public offsets or alignment metadata;
- structural typing across modules;
- methods, inheritance, traits, interfaces, or generics.
