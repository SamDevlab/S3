# M1.97 Test Evidence

`tests/test_m197_aarch64_object_link.py` covers deterministic ELF identity,
defined and unresolved symbols, `call26` relocation capture, explicit symbol
resolution, unsupported relocation rejection, and host-target rejection.

This is structural object/link evidence only. Linux AArch64 native object/link
and differential certification remain dependent on the required AArch64
toolchain runner and are not fabricated by this checkout.
