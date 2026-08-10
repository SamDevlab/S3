# Milestone 1.34 - FFI

This milestone establishes the first explicit foreign-function boundary for
S3. The initial contract is deliberately scalar-only and makes the native ABI
classification observable before call emission is added.

Supported types are `trit`, `tryte`, `i64`, and `f64`. Integer values use the
integer ABI class; `f64` uses the floating-point ABI class. External symbols
must be plain C-style identifiers. Strings, slices, references, pointers,
heap objects, variadic arguments, and implicit libc dependencies are outside
this boundary.
