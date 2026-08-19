# M1.88 Architecture

M1.88 upgrades Linux AArch64 from the earlier scalar/header probe to an explicit compiler-program backend route. `AArch64ProgramLowerer` consumes the complete public S3 Assembly opcode surface, emits bounded AArch64 assembly text for functions/control flow/calls, and routes complex runtime semantics through named target runtime helper symbols instead of pretending they were already encoded inline.

The Linux integration now accepts a complete `AssemblyProgram`, not only `emit_return(value)`. The target artifact records AArch64 assembly text, ELF64/AArch64 container identity, instruction count, and required runtime symbols. The instruction ceiling remains `100000`.

`AArch64ABIContract` records the V1 AAPCS64 boundary: 16-byte stack alignment, x0-x7 integer arguments, v0-v7 floating arguments, x8 indirect-result register, x29 frame pointer, x30 link register, and callee-saved x19-x28. A native build plan records runtime-symbol call relocations. The opt-in cross-platform backend registry can select Linux AArch64 alongside the historical Linux x86-64 default without silently changing the default builtin catalog.

A platform toolchain is represented by the bounded `AArch64NativeToolchainProvider` boundary. Actual assemble/link/native execution evidence is separate. On the campaign Windows host Linux AArch64 execution remains `DEFERRED_BY_ENVIRONMENT`; structural compiler-program lowering is not relabeled as native execution.
