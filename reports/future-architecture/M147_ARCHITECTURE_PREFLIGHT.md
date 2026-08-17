# M1.47 Architecture Preflight

Status: `CLOSED_WITH_BOUNDED_SCOPE`.

The interop layer is a consumer-side Python buffer-protocol adapter using the
Python Stable ABI. M1.47 does not export an S3-owned reallocating buffer to
Python and does not transfer ownership to Python.

Inputs are borrowed for the duration of one foreign call and are copied into
S3-owned storage when retention or mutation beyond that call is required.
Python may not retain an S3 view. S3-owned buffers may not reallocate while a
view is active. The initial view is one-dimensional, byte-format, C-contiguous,
with unit itemsize and no negative strides. Read-only input is accepted;
mutable access requires an explicitly writable buffer and remains call-scoped.

Strings are UTF-8 byte spans with explicit length; bytes and slices are
pointer-plus-length views only inside the call. Status is a fixed integer
success/failure result; detailed errors use the established closed error
payload and never Python exceptions as the S3 ABI. No callbacks, threads, or
GIL handoff are introduced.

This closure is supported by the Python buffer protocol requirement that a
successful buffer acquisition is paired exactly once with release and that
the consumer owns the acquired reference. See the official Python buffer
documentation: https://docs.python.org/3/c-api/buffer.html.
