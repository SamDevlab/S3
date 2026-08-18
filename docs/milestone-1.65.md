# Milestone 1.65 - Windows x86-64 Backend V1

## Architecture status

The repository-consistent target identifier is `windows-x86_64`. M1.65 adds a
closed Win64 ABI planning surface in `bootstrap.s3.windows_x86_64`: position-
based RCX/RDX/R8/R9 and XMM argument classes, 32-byte shadow space, 16-byte
stack reservation alignment, saved-register sets, and the distinction between
scalar return registers and S3 logical aggregate result slots.

The existing Linux `linux-x86_64` target and System V backend are unchanged.
The cross-platform catalog is opt-in; the default builtin catalog remains the
certified Linux target until PE code generation is available.

## Environment status

The local host has no `clang-cl`, `clang`, `lld-link`, `link.exe`, `ml64`, or
`llvm-mc`. Therefore PE/object emission and executable validation are
`DEFERRED_BY_ENVIRONMENT`. The fail-closed toolchain probe records this fact;
no PE output or Windows execution is claimed.

## Safety boundary

The plan preserves the S3 logical aggregate result-slot contract and does not
expose raw pointers or alter Linux semantics. Windows-specific source APIs,
DLL/COM/PDB integration, ARM64, and a fabricated fallback to System V are out
of scope.

## Tests

Focused tests cover target identity, Win64 register/stack classification,
shadow space and alignment, saved registers, scalar and aggregate result
transport, deterministic backend planning, and fail-closed toolchain
discovery. Existing Linux backend tests remain the non-regression gate.

## Implementation status and dependency

COMPLETE as the structural Win64 ABI/backend plan permitted by the available
toolchain. PE/object emission and Windows execution remain deferred. M1.66
consumes the target/provider boundary for cross-platform OS services.
