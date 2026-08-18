# Milestone 1.62 - Borrowed Slices and Views V1

## Architecture status

M1.62 closes bounded zero-copy views on top of the existing lexical borrow
model. Static arrays retain the source-language `&[T]` and `&mut [T]` ABI
(`base address` plus `i64 length`). The hosted dynamic owners now also expose
explicit ranged views for bytes, vectors, and text.

Views retain no ownership and block owner operations that could invalidate
storage. View indices are relative to the view. Bounds are checked before
access. Text views use byte offsets but require both endpoints to be valid
UTF-8 boundaries. Mutable text views are rejected because arbitrary byte
writes cannot preserve text validity; mutable byte/vector views remain legal.

## Out of scope

Raw pointer syntax, escaping views, lifetime parameters, owned slice results,
and dynamic-owner source-language slice construction remain out of scope.

## Validation

Focused tests cover static array slices, ranged vector/byte views, mutable
exclusivity, relative bounds, text byte length, UTF-8 boundaries, and O0/O1
array-slice execution. Existing reference and native slice contracts remain
part of the M1.62 T2/T3 gates.
