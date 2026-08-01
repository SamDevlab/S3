# Milestone 1.06 - Second-Stage Self-Hosting Components

Status: Selected - implementation pending in Draft PR #126

Milestone 1.06 continues the partial self-hosting path after ADR-0021 and
Milestone 1.05. Python remains the reference compiler and default path. S3
components added here are opt-in differential references only.

## Selection Rules

Selected components must be:

- small and pure;
- deterministic from scalar inputs;
- backed by an existing or newly stated Python reference in tests;
- executable through hosted O0 and O1;
- compatible with native ELF checks where the host supports them;
- free of filesystem, heap, dynamic text, aggregate returns, and default
  adoption.

At least one selected component must exercise Milestone 1.05 payload enums
without returning a multi-cell value.

## Selected Components

### Assembly Opcode Classifier

Status: existing first-stage differential component.

- S3 source: `selfhost/assembly/opcode_ids.s3` and
  `selfhost/assembly/opcode_classifier.s3`.
- Python reference: `tests/test_self_hosting_opcode_classifier.py`.
- Input: scalar opcode id and operand count.
- Output: scalar `trit`/`tryte` category, arity, variadic, and acceptance
  results.
- Error model: invalid ids return scalar sentinel values.
- Return cells: one scalar.
- Risk: low; already covered by O0/O1 and native harness tests.

### Diagnostic Classifier

Status: selected for 1.06 implementation.

- S3 source: `selfhost/diagnostics/diagnostic_classifier.s3`.
- Python reference: focused tests derived from `bootstrap.s3.diagnostics`
  category and phase enums.
- Input: scalar diagnostic category id and phase id.
- Output: scalar known/unknown, severity, and report-channel codes.
- Error model: invalid ids return scalar sentinel values.
- Return cells: one scalar.
- Milestone 1.05 usage: uses a local payload enum to classify known versus
  unknown probes, then matches the payload to produce scalar results.
- Risk: low; no formatting, message text, source spans, or JSON schema changes.

### Discriminant Layout Validator

Status: selected for 1.06 implementation.

- S3 source: `selfhost/layout/discriminant_validator.s3`.
- Python reference: focused tests over the public `tryte` discriminant range and
  simple fixed-width enum layout rules.
- Input: scalar discriminant, variant count, and payload width.
- Output: scalar validity, tag position, and total width checks.
- Error model: invalid ranges return scalar sentinel values.
- Return cells: one scalar.
- Risk: low; this does not inspect compiler internals or construct aggregate
  layouts.

## Rejected Candidates

- Full lexer: requires dynamic text, token streams, arrays, and diagnostics.
- Full parser: requires recursive ASTs, token streams, and structured
  diagnostics.
- Semantic analyzer: requires symbol tables, maps, module graphs, and broad
  diagnostics.
- Optimizer: too large and not a pure scalar component.
- Backend/linker/CLI/filesystem: outside the current self-hosting boundary.
- Diagnostic formatter: still blocked on dynamic text and serialization.

## Adoption Policy

No component becomes the default implementation in this milestone. Passing
differential tests only promotes a component to a reference candidate for later
campaigns.
