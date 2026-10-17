# S3 Embedded / Bare-Metal Foundation

Status: `EXPERIMENTAL=YES`, `PRODUCTION_READY=NO`, and
`REAL_BOARD_TESTS=NOT_RUN`. This isolated package models freestanding targets
without requiring Linux, Windows, macOS, a board, QEMU, or a driver.

`s3.target.freestanding.v1` separates architecture (`aarch64`, `riscv64`) from
board (`qemu-virt-aarch64`, `qemu-virt-riscv64`). It provides deterministic
memory maps, target descriptions, link sections, entry symbols, ELF/raw-image
artifact contracts, and SHA-256 canonical serialization. ELF is an object
format; Linux ABI remains a hosted concern.

MMIO is an explicit unsafe boundary with widths 8/16/32/64, alignment and
volatile access metadata. Volatile means accesses cannot be removed or freely
reordered according to the documented contract; it is not atomic or a thread
synchronization primitive. No syscall, libc, allocator, scheduler, driver,
interrupt, exception, timer, or multicore runtime is implemented.

AArch64 has a freestanding contract and reuses the existing architectural
direction conceptually; no parallel code generator was added. RISC-V64 has a
target/capability contract only; code generation is not implemented. QEMU and
real hardware are optional future oracles. Frontend/backend integration is
`POST_M3_FRONTEND_INTEGRATION=YES` and `POST_M3_BACKEND_INTEGRATION=YES`.

Roadmap: target/startup closure, AArch64 QEMU hello, RISC-V minimum backend and
QEMU hello, MMIO/volatile frontend, interrupts, embedded library, physical
board, MCU profile, multicore runtime, and the S3-native bare-metal path.
