# S3 IR and Assembly Format Compatibility Policy

This document defines versioning rules, compatibility constraints, and reader/writer guarantees for S3 IR JSON and S3 Assembly formats.

## Current Format Versions

- **S3 IR JSON Format Version**: `0.6.0`
- **S3 Assembly Format Version**: `.s3asm 0.7.0`
- **Diagnostic Schema Version**: `1.0.0`

## Versioning Rules (SemVer)

1. **MAJOR Bump (x.0.0)**:
   - Breaking structural changes to the IR schema or assembly syntax.
   - Removal or semantic redefinition of existing opcodes, types, or control-flow invariants.
   - Reader incompatibilities requiring explicit data migration tools.

2. **MINOR Bump (0.x.0 / 1.x.0)**:
   - Addition of new IR opcodes, assembly directives, or optional metadata fields that do not break backwards-compatible reading of existing valid constructs.
   - Extension of supported scalar or aggregate type constructors.

3. **PATCH Bump (x.y.z)**:
   - Formatting refinements, bug fixes in serialization output, or documentation clarifications that preserve strict AST and bytecode equivalence.

## Guarantees and Invariants

### Canonical Serialization

- S3 IR JSON and S3 Assembly writers MUST emit deterministic, canonical outputs.
- JSON keys are sorted deterministically without non-standard NaN/Infinity representation.
- Lines in S3 Assembly follow fixed indentation and canonical instruction signatures.

### Unknown Versions and Fields

- **Unknown Versions**: Readers MUST immediately reject IR or Assembly files declaring version strings newer than supported or incompatible major versions.
- **Unknown Fields**: Structurally invalid or unrecognized schema fields in IR JSON trigger explicit diagnostic errors (`S3C_IR_VERIFICATION_FAILED`) rather than silent ingestion.

### Backward Compatibility Promises

- Current readers for S3 Assembly `0.7.0` retain backward compatibility for `0.6.0` and legacy `0.5.0` files.
- Version `0.7.0` adds typed reference-parameter metadata and vector register declarations; older files retain their prior interpretation.
- Version `0.7.0` artifacts are the canonical target for new writers.

## Open Governance Decisions

> [!NOTE]
> ARCHITECTURE DECISION REQUIRED — LONG-TERM 0.5 DEPRECATION HORIZON:
> The exact timeline for sunsetting legacy 0.5.0 reader support will be established in a future milestone ADR after full self-hosting maturation.
