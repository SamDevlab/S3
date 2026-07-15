# S3 0.10 Roadmap: Python-to-S3 Migration

The 0.10 series is about preparing S3 for incremental self-hosting. It does not
replace the Python compiler in one step. Each delivery should be small,
testable, and reversible.

## 0.10-A: Self-hosting migration plan

Objective:

- document the migration plan, compiler inventory, language gaps, and bootstrap
  strategy.

Scope:

- `docs/self-hosting.md`;
- `docs/roadmap-0.10.md`;
- optional inventory tooling.

Out of scope:

- implementing a compiler component in S3;
- changing compiler behavior;
- changing language semantics.

Validation:

- documentation review;
- `git diff --check`;
- optional inventory tool execution.

Risks:

- documenting a path that is too broad to guide implementation;
- choosing early components that depend on language features S3 does not have.

## 0.10-B: Language gap inventory

Objective:

- map exactly which language features are missing before real compiler
  components can be written in S3.

Scope:

- strings;
- arrays or vectors;
- records;
- enums or sum types;
- modules and imports;
- file I/O boundaries;
- structured errors;
- deterministic serialization;
- tests for S3 programs.

Out of scope:

- implementing all missing features;
- replacing compiler stages.

Validation:

- a gap matrix tied to concrete compiler components;
- minimal examples that show what is already expressible and what is blocked.

Risks:

- underestimating text handling requirements;
- mixing language design decisions with component migration work.

## 0.10-C: Minimal S3 library foundation

Objective:

- start a minimal S3 library foundation for pure deterministic helpers.

Possible scope:

- simple helper functions;
- small deterministic data operations;
- formatting or normalization helpers once strings are available;
- examples that compile through the current Python compiler.

Out of scope:

- broad I/O;
- parser migration;
- backend migration;
- replacing default compiler behavior.

Validation:

- small S3 programs;
- `s3 check`;
- `s3 inspect`;
- golden inspect artifacts.

Risks:

- building helpers before the language has stable module boundaries;
- adding library code that cannot be reused by compiler components.

## 0.10-D: Module/import design

Objective:

- define and, if feasible, implement the minimum needed to organize S3 code
  across multiple files.

Scope:

- module names;
- import syntax and resolution rules;
- deterministic compilation order;
- clear boundaries for examples and future library code.

Out of scope:

- package management;
- external dependency resolution;
- broad host integration.

Validation:

- small multi-file examples;
- explicit error cases for missing or duplicate modules;
- stable inspect output for multi-file inputs when implementation exists.

Risks:

- making module rules too large for the current compiler;
- introducing path behavior before diagnostics and reproducibility are ready.

## 0.10-E: First compiler component candidate

Objective:

- choose the first small compiler component to migrate experimentally to S3.

Candidate components:

- Assembly renderer;
- IR normalizer;
- diagnostic formatter;
- small static checker.

Do not choose the full parser yet.

Scope:

- candidate selection;
- exact input and output contract;
- Python reference behavior;
- comparison strategy;
- acceptance criteria.

Out of scope:

- replacing the default Python component;
- migrating a broad subsystem.

Validation:

- written candidate contract;
- sample inputs and expected outputs;
- identified golden artifacts or comparison fixtures.

Risks:

- selecting a component that requires missing language features;
- choosing a component with unclear observable behavior.

## 0.10-F: Python vs S3 comparison harness

Objective:

- create a tool that compares Python component output with S3 component output.

Scope:

- deterministic text or structured output comparison;
- readable diffs;
- clear exit codes;
- small fixture set;
- future CI compatibility.

Out of scope:

- broad compiler replacement;
- running experimental components by default.

Validation:

- matching outputs return success;
- intentional mismatches return failure with readable diffs;
- no nondeterministic metadata in compared outputs.

Risks:

- comparing unstable text formats;
- hiding behavior differences behind formatting normalization.

## 0.10-G: First experimental S3 component

Objective:

- implement the first small compiler component in S3.

Scope:

- one narrow component selected in 0.10-E;
- compilation through the Python compiler;
- comparison against Python output;
- documentation of limitations.

Out of scope:

- default adoption;
- changing public compiler behavior;
- migrating unrelated components.

Validation:

- Python-vs-S3 comparison harness passes;
- golden inspect artifacts remain stable;
- diagnostic goldens remain stable when relevant.

Risks:

- language gaps forcing awkward encodings;
- output drift that is hard to distinguish from intentional formatting changes.

## 0.10-H: Optional adoption path

Objective:

- define a guarded way to use the S3 implementation experimentally.

Scope:

- internal selection mechanism;
- fallback to Python reference behavior;
- explicit validation before adoption;
- clear rollback path.

Out of scope:

- making the S3 component default automatically;
- removing the Python reference implementation.

Validation:

- reference path and experimental path both remain testable;
- comparison continues to run;
- golden artifacts remain stable unless intentionally updated.

Risks:

- enabling an experimental path too early;
- creating two diverging implementations without enough comparison coverage.
