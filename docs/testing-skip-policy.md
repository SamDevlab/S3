# S3 Testing Skip Governance Policy

This document defines the official skip governance policy for the S3 project test suite across all supported host platforms (Windows, Linux, macOS).

## Purpose

To ensure high quality, auditability, and prevention of silent test suite erosion, test skips must be categorized, documented, and governed by strict rules.

## Skip Categories

All skipped tests in the S3 repository must belong to one of the following official categories:

1. `WINDOWS_TOOLCHAIN`: Tests skipped on Windows hosts due to native toolchain differences (e.g. Linux ELF execution, raw x86-64 assembler/linker dependencies).
2. `LINUX_ONLY_ELF`: Tests requiring Linux ELF binary execution (`run-native`, standalone ELF binaries). Validated strictly in Linux CI jobs.
3. `OPTIONAL_EXTERNAL_TOOLCHAIN`: Tests requiring optional external toolchains (e.g. `gcc`, `clang`, `rustc`, `cargo`, `zig`).
4. `HISTORICAL_COMPATIBILITY`: Tests skipped for legacy V0.5 syntax or historical baseline checks replaced by updated specs.
5. `FEATURE_NOT_IMPLEMENTED`: Tests skipped because the corresponding language or toolchain feature is explicitly planned but not yet implemented.
6. `ENVIRONMENTAL`: Tests skipped due to host environment constraints (e.g. insufficient instruction limit, missing display).
7. `TEST_DESIGN`: Tests intentionally skipped as design markers or pending differential harnesses.
8. `UNKNOWN`: Unclassified skips (PROHIBITED without prior governance approval).

## Rules and Expectations

### Platform Expectations

- **Windows Hosts**: Hosted emulator tests, IR verification, CLI checks, frontend candidate probes, and benchmark infrastructure tests MUST PASS. Native ELF execution tests are expected to be skipped with reason `LINUX_ONLY_ELF` or `WINDOWS_TOOLCHAIN`.
- **Linux Hosts / CI**: Full test suite MUST PASS (0 failures). ELF native backend tests MUST run and pass.

### Prohibition of Unexplained Skips

- Every `@pytest.mark.skip` or `pytest.skip()` invocation MUST include an explicit `reason` string referencing the relevant category.
- Blank skip reasons or generic messages (e.g. `"skip for now"`) are strictly prohibited in code reviews.

### Review and Baseline Policy

- Any pull request introducing new skipped tests must specify the category and rationale in the PR description.
- A sudden increase in skipped tests on a given platform triggers a review requirement before PR merge.
- The difference between `unavailable` (toolchain missing gracefully handled by adapter) and `skipped` (test assertion bypassed) must be preserved in benchmark and test reporting.
