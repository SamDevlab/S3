# S3 Candidate-to-Default Component Promotion Policy

This document defines the formal criteria required before any candidate or self-hosted compiler component written in S3 can replace the default Python reference implementation.

## Default vs Candidate Status

- **Default Implementation**: `bootstrap-python` (Python reference implementation in `bootstrap/s3/`).
- **Candidate Components**: Experimental or self-hosted S3 modules (e.g. bounded assembly frontend candidate in `bootstrap/s3/assembly_frontend_candidate.py`, S3 opcode classifier, diagnostic classifier, layout validator).

> [!IMPORTANT]
> No candidate component is promoted to default in PR #129. Python remains the single source of truth and default path for all compilation and execution stages.

## Required Promotion Criteria

To promote a candidate component to default status in a future milestone, the candidate MUST meet all 12 objective criteria:

1. **Feature Parity**: 100% coverage of the target language subset and toolchain interfaces.
2. **Differential Parity**: 100% output identity against the reference Python implementation on the full test suite.
3. **Diagnostic Parity**: Identical diagnostic code, line, column, and message reporting on invalid inputs.
4. **Deterministic Output**: Byte-for-byte identical output regardless of compilation order, host OS, or invocation pattern.
5. **Performance Envelope**: Meets or exceeds the latency and memory efficiency of the default Python implementation.
6. **Backward Compatibility**: Fully compatible with existing IR JSON 0.6.0, Assembly 0.6.0, and CLI contracts.
7. **Rollback & Fallback Mechanism**: Clear flag-based fallback (`--use-reference-compiler`) to revert instantly if defects are discovered.
8. **CI Duration Impact**: Execution time of the candidate does not cause unacceptable CI slowdowns.
9. **Malformed Input Robustness**: Zero crashes (panic/uncaught exception) on fuzzing or malformed input corpora.
10. **Native Parity**: Full verification when linked as a native ELF executable under Linux x86-64.
11. **Repeated Stage Bootstrap**: Ability to compile itself in a self-hosting cycle producing bit-identical binaries.
12. **Formal ADR Acceptance**: Explicit architectural review and accepted ADR approving the promotion.
