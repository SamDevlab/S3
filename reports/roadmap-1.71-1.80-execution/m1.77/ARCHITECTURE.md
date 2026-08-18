# M1.77 - Linux AArch64 Native Backend V1 Architecture

## MILESTONE

`M1.77 LINUX_AARCH64_NATIVE_BACKEND_V1`

## PROBLEM

S3 needs a registered Linux AArch64 target and a reviewable ABI/ELF contract
without pretending that structural generation is native execution
certification.

## PUBLIC_SURFACE

`LINUX_AARCH64_TARGET`, `Aapcs64Call`, `AArch64Instruction`,
`AArch64ElfHeader`, and `AArch64Backend` provide target identity, argument
placement, structural text, and ELF header validation.

## OWNERSHIP_MODEL

The backend consumes immutable structural input and returns immutable text or
bytes. It exposes no raw pointers, host handles, or shared mutable state.

## RESOURCE_MODEL

Argument registers are bounded to x0-x7; additional arguments use aligned
stack slots. The structural emitter has a finite instruction budget.

## FAILURE_MODEL

Unsupported value classes, argument overflow, malformed ELF identity, and
instruction-budget violations are explicit `AArch64BackendError` values.

## LOWERING_MODEL

V1 lowers scalar integer return/argument contracts to AAPCS64 names and emits a
minimal `.text` skeleton. Full S3 Assembly lowering is a later backend unit;
this milestone does not route x86 programs through an unvalidated path.

## DETERMINISM_MODEL

Register and stack placement, instruction text, and ELF identity are fixed by
input order and have no host-dependent metadata.

## PLATFORM_MODEL

Target model is Linux AArch64 (`e_machine=183`, ELF64 little endian). Execution
certification requires an available AArch64 toolchain/runner and is reported
separately from implementation.

## OUT_OF_SCOPE

macOS/Mach-O, dynamic linking, syscalls, JIT, cross compilation installation,
and execution claims on a non-AArch64 host.

## TEST_STRATEGY

Focused structural tests cover target registration, AAPCS64 argument and
return placement, ELF identity, deterministic emission, invalid input, and
explicit environment deferment.
