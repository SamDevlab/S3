# Milestone 1.49 — Portable WASI Host and Target Contract

M1.49 defines the bounded internal target `wasm32-wasip1-s3`: a core
WebAssembly `.wasm` module using `wasi_snapshot_preview1`, certified by a
version-pinned Wasmtime runtime. It does not implement the Component Model,
WASI Preview 2, browser execution, or a second WASI generation.

Deliverables are the target manifest, canonical artifact policy, linear-memory
descriptor ABI, capability map, explicit error/exit model, and integration
with M1.45/M1.46. The exact normative contract is in
[`spec/wasi-target.md`](../spec/wasi-target.md) and ADR-0036.

Required environment: Linux x86-64, a version-pinned WebAssembly encoder or
backend, `wasm-tools` for validation, and Wasmtime for certification. None is
installed or provisioned by this campaign.

Acceptance is defined by `M149-G01` through `M149-G11`; the gates are not run
until the dedicated provisioning campaign completes.
