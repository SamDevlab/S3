# Milestone 1.34 - FFI

This milestone establishes the first executable foreign-function boundary for
S3. `foreign fn` declares a host-provided symbol and `export fn` exposes an
unmangled C ABI symbol. `ffi-build` emits a real Linux shared object.

Supported scalar types are `trit`, `tryte`, `i64`, and `f64`. Integer values
use the SysV integer ABI class and `f64` uses the floating-point class. Borrowed
primitive slices use the ABI pair `(base address, i64 length)` and are passed
without an S3 temporary copy. External symbols must be plain C-style
identifiers. Strings, heap ownership, variadic arguments, and implicit libc
dependencies remain outside this boundary.

Example:

```text
foreign fn host_add(a: i64, b: i64) -> i64

export fn sum(xs: &[i64]) -> i64:
    return xs[0] + xs[1]
```

The native proof covers C calling exported `i64`/`f64` functions, S3 calling
linked C `i64`/`f64` functions, Python `ctypes` loading the generated `.so`,
and host-owned mutable buffers observed after an `&mut` slice call.
