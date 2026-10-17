# S3 Accelerator Foundation

Status: `EXPERIMENTAL=YES`, vendor-neutral and hardware-agnostic. The isolated
`bootstrap.s3.accelerator` package defines `s3.accelerator.ir.v1` with a
portable GRID/WORKGROUP/WORKITEM execution model, 1D/2D/3D launch dimensions,
logical buffers and PRIVATE/WORKGROUP/GLOBAL/CONSTANT memory spaces.

The IR is deterministic, canonically serialized and SHA-256 addressed. It
validates workgroup bounds, duplicate kernels, buffer identity, barrier scope,
operation/type support and `FLOAT64` capability without silently changing
precision or falling back to CPU execution. Host orchestration and device
kernel contracts are separate.

`vector_add` and `saxpy` are canonical bounded fixtures; they are IR fixtures,
not GPU executions. SPIR-V is the first portable target direction, but no
SPIR-V module is emitted yet: `SPIRV_CONTRACT=PASS` and
`SPIRV_EMISSION=NOT_IMPLEMENTED`. PTX and HIP/ROCm are contracts only;
emission/runtime are not implemented. CUDA, ROCm, Vulkan, OpenCL, drivers and
SDKs are not core dependencies. `REAL_GPU_TESTS=NOT_RUN`.

Future roadmap: SPIR-V compute closure, kernel syntax/semantics, CPU reference
executor, PTX/HIP lowering, device discovery, memory/stream runtime, real
NVIDIA/AMD smoke tests, optimization research, and an S3-native accelerator
compiler path. Frontend integration is `POST_M3_INTEGRATION_REQUIRED=YES`.
