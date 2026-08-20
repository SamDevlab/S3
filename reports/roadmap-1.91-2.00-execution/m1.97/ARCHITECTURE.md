# M1.97 Architecture: AArch64 Object and Link Boundary

`AArch64NativeBuildPlan` now records defined symbols and every emitted `bl`
relocation. `AArch64ObjectLinker` validates the Linux AArch64 target, ELF64
identity, exact entry symbol, bounded symbol and relocation tables, and the
supported `call26` relocation set. Object and linked artifacts use deterministic
canonical manifests behind explicit ELF relocatable/executable identities.

The native assembler/linker remains an injected provider boundary. No host
linker is invoked by the structural implementation, and no structural artifact
is reported as native execution evidence.
