# Milestone 1.02 - Composition and Qualified Names

Status:
In progress

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
In progress

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
Not started

Scope:

- unified postfix loop;
- calls;
- indexing;
- member suffix;
- source spans;
- syntactic tests;
- no semantic resolution.

### 1.02-B3 - Qualified name resolution

Status:
Not started

Scope:

- semantic resolution for module symbols;
- enum variant resolution;
- invalid member-base diagnostics;
- no lowering.

### 1.02-B4 - Record member access

Status:
Not started

Scope:

- record member access behavior;
- record member diagnostics over resolved record categories;
- preservation of the 1.02-A composition limits.

### 1.02-B5 - Lowering and verification

Status:
Not started

Scope:

- lowering from resolved postfix identities;
- no backend name guessing;
- IR verification coverage.

### 1.02-B6 - O0/O1 and multi-module integration

Status:
Not started

Scope:

- hosted O0/O1 equivalence;
- multi-module integration;
- optimizer-boundary checks.

### 1.02-B7 - Native coverage

Status:
Not started

Scope:

- native x86-64 coverage where runtime behavior is affected.

## Later planned milestones

Status:
Planned

- 1.02-C - cross-module nominal types;
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
- previous functional/documental commit:
  `65acfd98ba4507d3e45f5388f57a08846a7b510d`;
- last completed unit: 1.02-B1;
- next unit: 1.02-B2 - Unified Postfix Parser and AST;
- first action next session: confirm branch, HEAD, working tree, PR, and CI
  before changing the parser;
- likely files to audit: `lexer.py`, `parser.py`, `ast.py`, and parser tests;
- runtime code changed by this checkpoint: none.
