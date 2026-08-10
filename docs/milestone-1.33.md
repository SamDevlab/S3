# Milestone 1.33 - Slices

This milestone establishes the shared checked slice-range contract on top of
the large-index domain introduced by M1.32.

## Contract

- ranges are half-open: `[start, end)`;
- both bounds are non-negative `LargeIndex` values;
- reverse ranges are rejected;
- range length is checked in the same large-index domain;
- index containment excludes the end bound;
- the existing static-text slice semantics retain their current diagnostics
  and behavior while consuming this domain contract.

The milestone does not introduce heap storage, references, raw pointers,
dynamic arrays, FFI, or the superseded heap-first roadmap.
