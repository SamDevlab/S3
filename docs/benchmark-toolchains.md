# Benchmark Toolchains And Environments

`s3bench` detects `clang`, `gcc`, `rustc`, `cargo`, `zig`, `ld`, and WSL with
explicit argument-list commands. Exact versions and flags are recorded. Missing
tools are `unavailable`; the harness never installs, simulates, or silently
substitutes them.

| Implementation | Unoptimized | Optimized |
| --- | --- | --- |
| S3 native | O0 | O1 |
| C11 | `-O0 -std=c11 -fno-strict-overflow` | `-O2 -std=c11 -fno-strict-overflow` |
| Rust | `-C opt-level=0 -C overflow-checks=on -C panic=abort` | `-C opt-level=2 -C overflow-checks=on -C panic=abort` |
| Zig | Debug | ReleaseFast |

These are available configurations, not equivalent optimizer capabilities.
`-march=native`, handwritten assembly, external crates, and platform-specific
intrinsics are excluded from the portable baseline.

Shared GitHub runners validate functionality only. An authoritative native
baseline requires one controlled Linux x86-64 environment for S3 O0/O1, C,
Rust, and Zig with identical inputs, workload versions, checksums, repository
SHA, power/background notes, and complete toolchain metadata. WSL remains a
distinct environment class.
