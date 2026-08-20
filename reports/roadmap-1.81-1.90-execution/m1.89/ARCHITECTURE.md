# M1.89 Architecture

M1.89 applies the same complete S3 Assembly program lowering surface to Darwin ARM64 while keeping platform identity separate. `MacOSArm64Integration.build_program()` and `build_macos_arm64_program()` emit Mach-O/ARM64-targeted AArch64 text with Darwin symbol spelling, bounded instruction count, runtime helper identities, and an explicit Mach-O 64 ARM64 container contract.

The shared AAPCS64-level value/call model is reused where Darwin permits it. `AssemblyType.F64` values use the floating-point ABI register class for parameters, calls, helper calls, results, constants, moves, and returns; integer/reference/value classes use x registers, and mixed signatures allocate each register class independently. Target symbol/container behavior is selected by the macOS route rather than copied from ELF. The cross-platform backend registry exposes a dedicated `macos-arm64` native-assembly provider and native build plan/toolchain boundary.

Native certification requires evidence bound to the exact structural artifact and executable hashes, target and toolchain identity, and the actual execution result. Raw caller-supplied exit/result values are not sufficient to flip an artifact to `NATIVE_CERTIFIED`.

This campaign host is Windows. Therefore assembler/linker and Apple Silicon execution certification remain `DEFERRED_BY_ENVIRONMENT`. Structural Mach-O identity and complete compiler-program lowering are recorded independently and are not described as a successful macOS execution certificate.
