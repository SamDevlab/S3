# Milestone 1.02 - Composition and Qualified Names

Status:
Complete

Milestone 1.02 stabilizes the language-composition contracts needed after
Milestones 0.97-1.01. It does not change the public IR, S3 Assembly, diagnostic
schema, ABI, CLI, golden artifacts, baselines, tags, releases, or public package
version by itself.

## 1.02-A - Record contract alignment

Status:
Complete

Supported record fields:

- `trit`;
- `tryte`;
- closed enums.

Rejected record fields and layouts:

- nested records;
- recursive record layouts;
- arrays;
- static or runtime strings;
- imported records as fields.

The 1.02-A unit aligned the public composition contract with the behavior
delivered by Milestone 1.00. See PR #124 and the contract in
[spec/composite-types.md](../spec/composite-types.md).

## 1.02-B - Postfix composition and qualified names

Status:
Complete

### B1 - Specification and ADR

Status:
Complete

Artifacts:

- [spec/postfix-expressions.md](../spec/postfix-expressions.md);
- [ADR-0018](decisions/ADR-0018-postfix-qualified-resolution.md);
- [spec/grammar.ebnf](../spec/grammar.ebnf);
- [spec/language.md](../spec/language.md);
- [spec/modules.md](../spec/modules.md).

B1 specifies postfix chaining, suffix precedence, source spans, evaluation
order, and the semantic distinction between module members, enum variants, and
record fields. It does not implement parser, AST, semantic, lowering, optimizer,
native, or runtime behavior.

### 1.02-B2 - Unified postfix parser and AST

Status:
Complete

Delivered:

- unified postfix loop;
- expression callees in `CallExpression`;
- left-associative call, indexing, slice, and member suffix composition;
- source spans;
- syntactic tests;
- compatibility helpers for simple unqualified calls.

### 1.02-B3 - Qualified name resolution

Status:
Complete

Delivered:

- deterministic resolution for `module.function(...)`;
- deterministic resolution for `module.Enum.Variant`;
- qualified enum variants in match labels;
- explicit rejection for modules, types, functions, and unsupported callees used
  as runtime values;
- no first-class functions or indirect calls.

### 1.02-B4 - Record member access

Status:
Complete

Delivered:

- record member access for literals, bindings, parameters, enum-valued fields,
  loops, match, and single-field record returns;
- `module.make().field` coverage when the qualified call returns a supported
  single-field record;
- record member diagnostics over resolved record categories, scalar values,
  arrays, enum values, function symbols, type symbols, and missing fields;
- preservation of the 1.02-A composition limits.

### 1.02-B5 - Lowering and verification

Status:
Complete

Delivered:

- qualified calls lower to concrete internal IR callees;
- qualified enum variants lower through existing enum discriminants;
- record member reads lower through existing scalarization;
- verifier coverage rejects unresolved textual callees and unknown member-like
  opcodes;
- no public IR or Assembly opcode was added.

### 1.02-B6 - O0/O1 and multi-module integration

Status:
Complete

Delivered:

- hosted O0/O1 equivalence;
- multi-module integration for qualified calls, qualified enum variants, record
  members, match, loops, record return member access, and rejection paths;
- optimizer-boundary checks;
- deterministic source unit ordering.

### 1.02-B7 - Native coverage

Status:
Complete

Delivered:

- native x86-64 O0/O1 coverage for qualified calls, qualified enum match,
  record fields, branch/loop composition, and qualified single-field record
  return member access.

## 1.02-C - Cross-module nominal types

Status:
Complete

Goal:

Allow exported nominal record and enum types to be used across module
boundaries while preserving deterministic identity and layout.

### C1 - Specification and ADR

Status:
Complete

Artifacts:

- [ADR-0019](decisions/ADR-0019-cross-module-nominal-type-identity.md);
- [spec/modules.md](../spec/modules.md);
- [spec/composite-types.md](../spec/composite-types.md);
- [spec/postfix-expressions.md](../spec/postfix-expressions.md);
- [spec/grammar.ebnf](../spec/grammar.ebnf).

C1 defines nominal identity as `ModuleId + TypeName`, chooses explicit
`export record` and `export enum` visibility, keeps type import aliases and
general reexports out of scope, and states that imported records remain invalid
as fields until the nested-record milestone.

### C2 - Module graph and type symbols

Status:
Complete

Delivered:

- exported type symbols in the module graph;
- separate function and type namespaces;
- private and missing type diagnostics;
- deterministic type symbol ordering.

### C3 - Imported nominal values

Status:
Complete

Delivered:

- imported enum values and match;
- imported record variables, parameters, single-field returns, construction,
  copies, and field access;
- module-qualified type annotations and record constructors;
- same-name nominal incompatibility across modules;
- preservation of imported record-as-field rejection.

### C4 - Layout

Status:
Complete for the current scalar ABI

Delivered:

- layout owned by the defining module;
- record field order preserved from the defining declaration;
- same-name and same-shape records in different modules remain distinct;
- enum discriminants preserved from defining variant order;
- deterministic layout across repeated compilation and source-unit order;
- explicit rejection of imported multi-field record returns before lowering.

### C5 - Differential and native coverage

Status:
Complete for the current scalar ABI

Delivered:

- native imported nominal type coverage;
- shared O0/O1 corpus for imported nominal records and enums;
- emulator coverage for the same corpus;
- Linux x86-64 ELF coverage through the `native-x86-64` CI job;
- coverage for imported single-field record returns, qualified constructors,
  enum values, multi-field record parameters, inverted source order, and
  aggregate-return rejection.

### C6 - Documentation and consolidation

Status:
Complete

Delivered:

- this milestone plan now reflects C1-C6 as complete;
- [docs/roadmap.md](roadmap.md), [README.md](../README.md), and
  [docs/self-hosting.md](self-hosting.md) now describe the completed 1.02
  language-composition contracts;
- [spec/modules.md](../spec/modules.md),
  [spec/composite-types.md](../spec/composite-types.md), and
  [spec/language.md](../spec/language.md) explicitly state the cross-module
  nominal type, scalarization, and aggregate-return limits;
- no new ADR was required beyond ADR-0018 and ADR-0019.

## Later planned milestones

Status:
Planned

- 1.03 - acyclic nested records;
- 1.04 - fixed-capacity text;
- 1.05 - payload enums and structured errors;
- 1.06 - additional self-hosting components.

## Explicitly unsupported

- nested records;
- imported record fields;
- arrays and strings as record fields;
- recursive layouts;
- methods;
- generics;
- heap;
- package manager;
- complete self-hosting.
- type import aliases;
- wildcard imports;
- general reexports;
- aggregate-return ABI changes.

## Completion criteria

- unified postfix parser and AST;
- semantic resolution for qualified names and member bases;
- lowering without backend name guessing;
- O0/O1 hosted equivalence;
- native x86-64 coverage;
- green CI;
- aligned documentation.

## Resume checkpoint

- branch: `campaign-1.02b-1.06-language-composition`;
- Draft PR: #125;
- latest 1.02-C functional/test commit:
  `2e6d0f46293785427f4af500cc85b31c41e0afac`;
- last completed unit: 1.02-C6;
- next unit: 1.03-A - Acyclic nested record architecture audit;
- first action next session: confirm branch, HEAD, working tree, PR, and CI
  before changing nested-record semantics;
- likely files to audit: `module_compilation.py`, `semantic.py`,
  `lowering.py`, module tests, composite tests, and native integration tests;
- public format changes by 1.02: none.
