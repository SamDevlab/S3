# S3 Quantum Foundation

Status: **EXPERIMENTAL**. This isolated prework is not a dependency of M3.00,
does not claim quantum advantage, and has no production or real-QPU support.

The provider-neutral `bootstrap.s3.quantum` package defines versioned
`s3.quantum.ir.v1` with structural validation, deterministic canonical JSON
bytes, and SHA-256 digests. Qubits are logical values; no copy operation is
provided, leaving ownership/aliasing rules open for a future semantic type
system. Existing classical trits are not qutrits; qutrit/qudit are extension
points only.

The experimental OpenQASM 3.1 emitter supports the V1 gate set and fails closed
through capability validation. QIR is currently a contract only: Base Profile
is modeled, but no fake LLVM/QIR is emitted. Providers are protocols with no
SDK or network dependency. A simulator is deferred until after M3.00.

Roadmap: IR closure, OpenQASM closure, semantic quantum types, reference
simulator, QIR Base Profile lowering, adaptive control, device discovery,
provider adapter, real-QPU smoke, then an S3-native compiler path.

`PYTHON_REFERENCE_IMPLEMENTATION=YES`; `REAL_QPU_TESTS=NOT_RUN`;
`PRODUCTION_PROMOTION=NO`; `POST_M3_INTEGRATION_REQUIRED=YES` for any invasive
frontend or shared-IR integration.
