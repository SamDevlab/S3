# M1.78 - macOS ARM64 Native Backend V1 Architecture

## MILESTONE

`M1.78 MACOS_ARM64_NATIVE_BACKEND_V1`

## PROBLEM

S3 needs an explicit macOS ARM64 target and Mach-O identity without conflating
Darwin object format with the Linux ELF backend.

## PUBLIC_SURFACE

`MACOS_ARM64_TARGET`, `MacOSArm64Backend`, and `MachOHeader` provide target
catalog identity, shared AAPCS64 scalar placement, deterministic Mach-O
header structure, and an execution certification status.

## OWNERSHIP_MODEL

Structural artifacts are immutable values. No host file descriptor, raw
pointer, or process handle is exposed by the target model.

## RESOURCE_MODEL

The backend uses the same bounded scalar instruction budget as M1.77 and
rejects unsupported structural inputs before emitting bytes.

## FAILURE_MODEL

Invalid CPU identity, malformed magic, unsupported return values, and limit
violations are explicit `MachOBackendError` values.

## LOWERING_MODEL

Scalar ABI placement reuses the AAPCS64 contract, while object-format identity
is emitted by a dedicated Mach-O header. Linux ELF code is not reused as a
Darwin binary.

## DETERMINISM_MODEL

Header fields and assembly text contain no timestamps, UUIDs, paths, or host
metadata. Repeated emission is byte-for-byte stable.

## PLATFORM_MODEL

Target is Darwin ARM64 (`CPU_TYPE_ARM64=0x0100000c`). Execution certification
requires a macOS ARM64 environment and is deferred on this Windows host.

## OUT_OF_SCOPE

Code signatures, signing identities, dynamic loader commands, Objective-C
runtime integration, and Linux execution.

## TEST_STRATEGY

Focused structural tests cover target registration, deterministic Mach-O
identity, ABI reuse, malformed header rejection, and explicit execution
deferment.
