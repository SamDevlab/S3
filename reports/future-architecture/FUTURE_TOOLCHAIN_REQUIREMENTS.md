# Future Toolchain Requirements

M1.47 requires a Linux x86-64 C compiler/linker and Python development
headers/libs sufficient for the selected Stable ABI adapter.

M1.49 requires a version-pinned WASM encoder/backend, a version-pinned WASI
runtime, and a documented runtime matrix. The exact packages remain unresolved
with M1.49.

M1.50 requires the M1.45/M1.46 tools, a native Linux toolchain, and the M1.49
toolchain only if the portable artifact gate is retained.

No installation or provisioning was performed.
