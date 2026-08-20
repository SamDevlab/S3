# M1.99 Architecture: Native Self-Move Lowering

`AssemblyProgram` remains semantically intact. The public candidate-analysis
helper reports `TMOV rN, rN` sites without deleting logical Assembly
instructions, so emulator behavior, diagnostics, resource limits, and
instruction accounting remain unchanged.

On x86-64, the emitter preserves the logical instruction instrumentation. When
the existing definite-initialization proof establishes that the self-read is
safe, only the physical value copy is omitted. When the proof is not available,
the emitter keeps the fail-closed initialization check. Non-self moves,
address-taken registers, calls, and non-definite branch joins remain
conservative.

AArch64 does not apply Assembly-level self-move deletion. Its current M1.99
optimization status is `DEFERRED`; the lowerer receives the original Assembly
program unchanged.

No native speedup claim is made. The Windows benchmark measures hosted Emulator
execution and uses native x86 generation only as a supplementary structural
probe.
