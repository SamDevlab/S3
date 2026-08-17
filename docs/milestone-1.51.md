# Milestone 1.51 - Composite Owned Values

Status: `ARCHITECTURE_CLOSED`.

`IMPLEMENTATION_NOT_STARTED`.

M1.51 closes the architecture for dynamic owned leaves inside explicit S3
aggregates. It does not modify parser, semantic analysis, IR, lowering,
emulator, optimizer, native code, FFI, or runtime behavior.

## Normative references

- [ADR-0037](decisions/ADR-0037-m1.51a-composite-owned-values.md)
- [Composite owned values specification](../spec/composite-owned-values.md)
- [M1.51A architecture report](../reports/m1.51-architecture/M151A_ARCHITECTURE_REPORT.md)

## Closed architecture

- Ownership unit: whole aggregate.
- Aggregates: records, enum payloads, static arrays, and nested fixed
  aggregates.
- Owned leaves: `bytes`, `text`, `tryte_vector`, `i64_vector`, `f64_vector`,
  `i64_map`, and `i64_set`.
- Dynamic collections of arbitrary owned aggregates: unsupported.
- Layout: inline fields with target-native alignment; no outer descriptor.
- x86-64 dynamic leaf: private 24-byte, 8-byte-aligned
  `base,length,capacity` descriptor.
- Owned parameters: indirect internal transfer to the callee.
- Owned returns: caller-provided result slot / hidden internal sret.
- Move: destructive whole-aggregate transfer.
- Partial field move: forbidden in M1.51.
- Borrow: lexical field projection; active projections block conflicting move
  and drop.
- Replacement: evaluate new, drop old, then move new.
- Clone: explicit deep recursive clone.
- Drop: static recursive glue, exactly once, reverse declaration/index order.
- FFI: owned aggregates do not cross C.
- GC, reference counting, raw pointers, traits, and general generics: not
  introduced.

## Boundary with M1.52

M1.52 owns field-sensitive, path-dependent aggregate ownership flow: partial
field moves, conditional reinitialization, join/backedge state, edge cleanup,
and verifier-complete exactly-once cleanup across control-flow exits. M1.52
must consume the M1.51 layout and ABI decisions rather than reopen them.

## Future implementation order

The implementation campaign is expected to proceed in this order:

1. legal owned aggregate type metadata and declaration validation;
2. canonical ownership-aware layout identity;
3. typed IR aggregate identity and ownership operations;
4. aggregate construction and whole-value moves;
5. field borrow projection and replacement transactions;
6. recursive clone and drop glue;
7. indirect parameters and caller-provided result slots;
8. whole-aggregate CFG verification;
9. emulator parity and failure cleanup;
10. x86-64 physical layout/lowering;
11. O0/O1 and deterministic diagnostics;
12. focused milestone evidence followed by broader integration gates.

No step above is executed by this architecture-closure campaign.

## Test policy

Architecture-only validation uses T0 sanity and directly impacted T1
documentation/schema/tooling checks. T2 and above are deferred until actual
implementation changes exist. No full suite or benchmark is required here.
