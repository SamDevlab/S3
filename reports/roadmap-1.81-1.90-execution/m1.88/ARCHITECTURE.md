# M1.88 Architecture

M1.88 integrates the existing Linux AArch64 backend contracts into an explicit
target artifact surface. The integration produces AAPCS64 scalar assembly and
an ELF64 AArch64 header through the same bounded instruction policy used by
the backend. Target identity, artifact format, and execution certification are
reported separately.

The current Windows host has no Linux AArch64 execution environment. Structural
generation and artifact validation are therefore certified locally, while
native execution remains explicitly `DEFERRED_BY_ENVIRONMENT`. No emulator or
x86 execution is relabeled as AArch64 evidence.
