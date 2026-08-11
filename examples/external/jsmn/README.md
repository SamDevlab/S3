# jsmn behavioral port experiment for S3

This directory contains a clean behavioral reimplementation of the core tokenization contract of [`zserge/jsmn`](https://github.com/zserge/jsmn) using S3 source code.

The experiment does **not** vendor or translate `jsmn.h` line by line. The upstream project is used as the behavioral reference for token kinds, token boundaries, token `size` semantics, default non-strict primitive handling, string escapes, and the public error codes.

Upstream jsmn is MIT licensed. Copyright for upstream jsmn remains with Serge Zaitsev and its contributors.

## Current S3 shape

`jsmn_demo.s3` is intentionally a fixed-capacity, zero-allocation kernel:

- input buffer: `tryte[96]` containing byte values;
- token capacity: 32;
- token fields are stored as parallel `tryte[32]` arrays;
- token kinds match jsmn: object `1`, array `2`, string `4`, primitive `8`;
- status codes match jsmn: no-memory `-1`, invalid `-2`, partial `-3`;
- an internal parent array is used only to preserve jsmn's `toksuper`/token-size behavior;
- default non-strict jsmn behavior is the compatibility target;
- no heap, raw pointer, network, file, or host-service dependency is introduced.

The checked test corpus rewrites only the fixed input declaration, executes the same S3 parser kernel, captures the final S3 memory buffers, and compares every emitted token field with an independent Python behavioral oracle. The oracle intentionally follows upstream behavior rather than strengthening jsmn into a full JSON validator; for example, raw control bytes inside a quoted token are not rejected by upstream `jsmn_parse_string` unless they participate in an invalid escape.

A dedicated Linux x86-64 test also compiles the unchanged demo kernel under O0 and O1, compares its return value with the hosted emulator, builds an ELF through the S3 native toolchain, and executes that ELF.

## Why this is inline today

The S3 language can mutate local fixed arrays and capture them in the hosted validation harness, but its current public source-level library boundary does not yet expose a jsmn-like caller-owned mutable token slice with pointer arithmetic. Keeping the parser state and token buffers in one S3 frame avoids pretending that capability exists.

This is therefore a real external workload/conformance kernel, not yet a drop-in C ABI replacement for `jsmn_parse`.

## Deliberate limits of this stage

The first port does not claim every optional jsmn API/configuration mode. In particular it currently provides:

- one-shot parsing only, not resumable incremental `jsmn_parser` state across calls;
- a fixed token pool rather than caller-selected capacity at runtime;
- default non-strict behavior, not a `JSMN_STRICT` mode switch;
- an allocated token pool, not jsmn's `tokens == NULL` count-only mode;
- no C ABI-compatible `jsmn_parse` export yet.

Those are API-surface limits, not hidden test substitutions. The tokenization kernel itself is exercised through S3 compilation and execution.

## Success criteria for this stage

1. Compile the parser in S3 O0 and O1.
2. Match jsmn token type/start/end/size on representative flat, nested, escaped, Unicode-escape and non-strict fixtures.
3. Match `JSMN_ERROR_NOMEM`, `JSMN_ERROR_INVAL`, and `JSMN_ERROR_PART` on representative failures.
4. Keep the implementation allocation-free and deterministic.
5. Execute the representative kernel as native Linux x86-64 under O0 and O1.
6. Use the workload later as an external S3 O0/O1/native/register-allocation benchmark without changing the JSON inputs to favor S3.

A later stage can turn this kernel into a reusable zero-copy API when S3 has a stable caller-writable borrowed-buffer/slice boundary suitable for that contract.
