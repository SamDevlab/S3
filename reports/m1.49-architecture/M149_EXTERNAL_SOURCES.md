# M1.49 External Evidence

`WebAssembly Specifications` — https://webassembly.org/specs/ — establishes
that core WebAssembly module semantics are independent of an embedding and
that WASI is an embedding interface layer.

`WebAssembly/WASI repository` — https://github.com/WebAssembly/WASI —
establishes the distinction between the widely used `wasi_snapshot_preview1`
API and the modular Preview 2 direction.

`Wasmtime Preview 1 API` — https://docs.wasmtime.dev/api/wasmtime_wasi/p1/index.html
— establishes an official Wasmtime Preview 1 binding for
`wasi_snapshot_preview1`.

`Wasmtime CLI` — https://docs.wasmtime.dev/cli.html — establishes an official
CLI execution path for WASI modules.

`Component Model repository` — https://github.com/WebAssembly/component-model
— establishes that Component Model introduces canonical lift/lower and a
separate component ABI, which is why it is not silently mixed into this core
module milestone.
