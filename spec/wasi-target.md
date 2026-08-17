# M1.49 WASI Target Contract

## Identity and artifact

The internal target is `wasm32-wasip1-s3`. Its artifact is one core
WebAssembly binary with `.wasm` extension and `wasi_snapshot_preview1`
imports. Components and WASI Preview 2 are not part of this milestone.

The canonical artifact contains no timestamps, absolute paths, producer
strings, debug sections, unordered custom sections, or environment-derived
metadata. Sections and exports are emitted in stable source/ordinal order.
The artifact identity is the M1.45 source/lock hash plus target, profile,
compiler version, and canonical encoder version. Cross-toolchain byte identity
is not promised; same locked S3 compiler/toolchain inputs must be byte-identical.

## Representation

| S3 value | Core representation |
|---|---|
| trit/tryte | i32 values after semantic range validation |
| i64 | i64 |
| f64 | f64 |
| owned bytes/text | guest descriptor `{i32 offset, i32 length, i32 capacity}` |
| borrowed bytes/text | call-scoped descriptor; no ownership transfer |
| structured status/error | i32 status plus explicit guest error descriptor |

Linear memory is guest-owned and allocated only by the S3 module allocator.
Offsets are unsigned 32-bit byte offsets, lengths/capacities are nonnegative
32-bit values, and descriptor arithmetic is checked. Memory grows only through
the allocator, never implicitly during a borrowed view. The initial maximum is
64 MiB; exceeding it is a deterministic resource error.

## Host contract

The initial import set is the smallest selected subset of
`wasi_snapshot_preview1`: `args_sizes_get`, `args_get`, `environ_sizes_get`,
`environ_get`, `fd_read`, `fd_write`, `fd_close`, `fd_seek`, `path_open`,
`path_filestat_get`, `proc_exit`, and the M1.48 TCP provider only if its exact
provider adapter is available. Clocks, randomness, polling, sockets outside
the M1.48 profile, process spawning, and ambient filesystem calls are forbidden.

Filesystem access is preopened and capability-scoped. Paths are relative to a
declared preopened root; traversal and undeclared rights fail deterministically.
Environment and argv are supplied by the runner only when declared.

Invalid UTF-8, invalid descriptors, denied capabilities, unsupported imports,
resource exhaustion, timeout, and host failures become explicit S3 result/error
values. `proc_exit` is reserved for the S3 main result: zero is success,
nonzero is the declared process result; traps remain distinct from process
exit and host failures.

The M1.46 runner owns the outer timeout. Provider operations use the M1.48
millisecond timeout. Runtime fuel/epoch limits are safety mechanisms and do
not replace the logical 100000-instruction S3 limit.

## Gates

- `M149-G01` target identity and import manifest validation
- `M149-G02` deterministic artifact bytes from identical locked inputs
- `M149-G03` Wasmtime execution of a no-host portable fixture
- `M149-G04` argv/environment allow and deny behavior
- `M149-G05` preopened filesystem rights and traversal denial
- `M149-G06` bytes/text and invalid-UTF-8 behavior
- `M149-G07` explicit errors, traps, exit status, and resource limits
- `M149-G08` timeout behavior at runner and provider layers
- `M149-G09` hosted/WASI observable-result equivalence
- `M149-G10` M1.45 build and M1.46 report integration
- `M149-G11` M1.50 renderer portable execution

No gate is executed by this architecture campaign.
