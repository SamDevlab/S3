# M1.65 Architecture Preflight

## Existing backend

The only registered native backend is `linux-x86_64` and its emitter/runtime
are System V Linux ELF specific. The backend registry rejects unknown targets,
and the builtin target catalog intentionally contains only the certified Linux
target. Reusing that emitter for Windows would produce incorrect ABI and
runtime claims.

## Selected boundary

Use the established spelling `windows-x86_64`. Add an opt-in cross-platform
target catalog and a structural Win64 ABI planner. It models position-based
argument registers, shadow space, aligned stack arguments, saved-register
classes, and the S3 logical result-slot transport. Keep the default registry
and Linux target unchanged until PE assembly/object emission exists.

## Toolchain result

Natural discovery on this Windows host found no `clang-cl`, `clang`,
`lld-link`, `link.exe`, `ml64`, or `llvm-mc`. Per campaign policy, no large
toolchain is installed and no PE execution is simulated. The milestone will
record `DEFERRED_BY_ENVIRONMENT` for PE/object/executable certification.
