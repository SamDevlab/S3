# M1.62 Architecture Preflight

## Findings

- The parser, semantic model, IR, verifier, emulator, and native backend
  already implement lexical `&[scalar]` and `&mut [scalar]` slices for static
  arrays.
- Hosted `DynamicBytes`, `DynamicText`, and `DynamicVector` already track
  active shared/mutable borrows and prevent resizing or owner mutation while a
  view is live.
- Dynamic collection descriptors are not source-language slice values, so
  inventing a new descriptor or pointer escape would exceed this milestone.

## Decision

Add ranged hosted views using the existing owner borrow counters. Keep the
source-language ABI unchanged. Text views are byte-oriented and require UTF-8
boundary endpoints; they are shared/read-only in V1.

## Gate

Run T0, direct M1.62 tests plus existing slice/reference tests at T1, the
M1.62 subsystem set at T2, and a cross-subsystem slice/IR/native shard at T3.
