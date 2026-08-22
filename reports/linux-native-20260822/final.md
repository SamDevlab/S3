# Linux Native Evidence 2026-08-22

## Exact source

- S3 source: `6604b9d07c607579df9c5c0759d8f2a708ba72d1`
- Evidence guest checkout: `/home/vboxuser/S3-m221-m235-git-20260822`
- Checkout clean: `YES`
- Guest: Linux x86_64 virtual machine
- Python: `3.14.4`
- Git: `2.53.0`
- Compiler: GCC `15.2.0`; Clang `21.1.8`; GNU ld `2.46`
- CPUs: `3`
- Memory: `8234 MB`

## Results

- `compileall`: `PASS`
- Hosted emulator/native x86_64 matrix: `PASS`
- Real Linux shared-library FFI through `ctypes`: `PASS`
- Fresh-process hash-seed determinism for generated docs: `PASS`
- Linux pytest focused suite: `NOT_AVAILABLE`

The guest Python installation has no pytest module. No package installation,
network dependency, sudo, service mutation, reboot, or shutdown was used. The
Windows focused T1-T3 gates therefore remain the pytest evidence for the
Python-level suite, while the guest supplies independent native/FFI evidence.
