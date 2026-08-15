# Evidence Ledger: S3 Roadmap 1.39-1.50

## Internal evidence

| ID | Evidence | Finding |
| --- | --- | --- |
| I01 | `README.md:19-55` | Current published surface is trit/tryte, static arrays/text, records/enums, checked IR, emulator, and Linux x86-64 native; no heap/global memory. |
| I02 | `README.md:102-116` | Aggregate internal results and bounded Assembly frontend exist, but dynamic text, filesystem, and complete self-hosting remain absent. |
| I03 | `docs/ai-agent-guide.md:33-40` | Explicit negative contract for heap, pointers, dynamic arrays/text, generics, exceptions, concurrency, threads, and async. |
| I04 | `docs/language-gaps.md:39-67` | Runtime text, reusable collections, test harness, maps, stdlib, and controlled file I/O are older documented gaps; portions of this file are stale about later modules/records/enums. |
| I05 | `docs/architecture.md:212-224` | Frame-local memory and no heap/aliasing are architectural constraints; MemorySSA is prototype/partial. |
| I06 | `docs/structured-data-capabilities.md` | Nominal records/enums and fixed layouts exist; generics, reflection, heap, pointers, exceptions, and implicit propagation do not. |
| I07 | `bootstrap/s3/dynamic.py:1-60` | M1.35 is a closed scalar `DynamicValue`, not source-level dynamic data. |
| I08 | `bootstrap/s3/host_services.py:16-50` | M1.36 is an injectable Python registry with two closed service IDs and scalar arguments/results. |
| I09 | `bootstrap/s3/project_container.py:17-52` | M1.37 validates sorted units and hashes a structural manifest; it does not resolve dependencies. |
| I10 | `bootstrap/s3/s3_docker.py:17-40` | M1.38 validates a deterministic Docker argv contract only; real Docker execution is not established. |
| I11 | `bootstrap/s3/ffi.py:14-60` | M1.34 FFI is scalar-only with explicit integer/float ABI classification. |
| I12 | `tests/test_external_jsmn_s3.py:12-18,134-190,253-258` | A real bounded fixed-capacity buffer workload is differential-tested, proving a useful kernel but not dynamic input. |
| I13 | `docs/self-hosting.md` and `selfhost/README.md` | Python remains compiler/reference; S3 candidates are opt-in differential components without fs/heap/dynamic text. |
| I14 | `docs/arm64-feasibility.md:1-59` | ARM64 requires a separate backend/runtime/toolchain/CI effort and is not currently supported. |
| I15 | `spec/source-syntax-0.6.md:121` | Package-manager and wildcard/conditional import behavior are outside the current source contract. |
| I16 | `pyproject.toml:12-33` | Python has no runtime dependencies; pytest is a development dependency and there is no S3 user test command. |

## External primary sources

| ID | Source | Architectural use |
| --- | --- | --- |
| E01 | [Rust generics](https://doc.rust-lang.org/book/ch10-00-generics.html) | Generics/traits solve reuse and behavior constraints; S3 should adopt only a smaller mechanism if duplication becomes measured. |
| E02 | [Rust error handling](https://doc.rust-lang.org/stable/book/ch09-00-error-handling.html) | Recoverable result versus unrecoverable panic supports explicit error flow without exceptions. |
| E03 | [Rust Cargo workspaces](https://doc.rust-lang.org/cargo/reference/workspaces.html) | Workspace identity and shared build context inform project graph design. |
| E04 | [Cargo resolver](https://doc.rust-lang.org/cargo/reference/resolver.html) | Lock/resolver behavior is evidence for reproducible dependency closure. |
| E05 | [Zig language reference](https://ziglang.org/documentation/master/) | Explicit allocators, comptime boundaries, and a conventional systems model inform visible resource policy. |
| E06 | [Python buffer protocol](https://docs.python.org/3/c-api/buffer.html) | A bounded zero-copy/borrowed contiguous buffer boundary is a concrete Python interop target. |
| E07 | [Python Stable ABI](https://docs.python.org/3.13/c-api/stable.html) | Stable ABI avoids binding to changing object layouts; it supports a limited C/Python boundary. |
| E08 | [POSIX open](https://pubs.opengroup.org/onlinepubs/9799919799/functions/open.html) | File descriptors, flags, errors, and close/resource semantics are explicit. |
| E09 | [POSIX general definitions](https://pubs.opengroup.org/onlinepubs/9799919799/functions/V2_chap02.html) | Thread safety, process and socket conventions, and standard host boundaries inform provider design. |
| E10 | [POSIX sockets](https://pubs.opengroup.org/onlinepubs/9799919799.2024edition/basedefs/sys_socket.h.html) | Socket descriptor and byte-stream contract supports M1.48. |
| E11 | [C++ ranges](https://eel.is/c%2B%2Bdraft/range.range) | Iteration and borrowed-range semantics show why collection views need explicit lifetime rules. |
| E12 | [C++ coroutine proposal](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2019/p0912r5.html) | Async/coroutine machinery is a high semantic commitment and is not a pre-1.50 default. |
| E13 | [WG14 atomics rationale](https://open-std.org/jtc1/sc22/wg14/www/docs/n1479.htm) | Memory ordering/data-race semantics make atomics a separate research campaign. |
| E14 | [Go modules reference](https://go.dev/ref/mod) | Module graph and minimal version selection demonstrate deterministic dependency identity. |
| E15 | [Go go.mod reference](https://go.dev/doc/modules/gomod-ref) | Manifest/requirement semantics inform a small local project graph. |
| E16 | [LLVM LangRef](https://llvm.org/docs/LangRef.html) | Target-independent IR and target triples support separating source core from target backends. |
| E17 | [LLVM source-level debugging](https://llvm.org/docs/SourceLevelDebugging.html) | Source/debug metadata is a later capability, not an excuse to expand M1.50 into a debugger. |
| E18 | [WebAssembly specifications](https://webassembly.org/specs/) | Core WebAssembly is portable computation with host interfaces layered separately. |
| E19 | [WebAssembly Component Model explainer](https://github.com/WebAssembly/component-model/blob/main/design/mvp/Explainer.md) | Canonical ABI and lift/lower boundaries inform byte/text/error interop. |
| E20 | [WASI capabilities](https://github.com/WebAssembly/WASI/blob/main/docs/Capabilities.md) | Explicit host authority matches S3's injectable capability direction. |

## Workload-to-evidence ledger

| Workload | Blocking facts | Selected milestones |
| --- | --- | --- |
| Scientific CLI | `README.md:23-31`; no runtime input/large buffers/interop. | 1.39, 1.40, 1.42, 1.47 |
| C/Python native library | `bootstrap/s3/ffi.py:30-44`; scalar-only. | 1.39, 1.42, 1.43, 1.47 |
| File utility | `docs/milestone-1.36.md`; no source file handles. | 1.39, 1.42-1.44 |
| Network service | no socket source/provider evidence. | 1.39, 1.42-1.44, 1.48 |
| Compiler/tooling | `docs/self-hosting.md`; Python remains reference. | 1.39-1.46, 1.50 |
| Large buffers | fixed JSMN capacity in `tests/test_external_jsmn_s3.py`. | 1.39, 1.40, 1.43, 1.47 |
| Container service | `bootstrap/s3/s3_docker.py` is spec-only. | 1.39-1.48; Docker validation deferred |
| Portable app | `docs/arm64-feasibility.md`; native x86-64 only. | 1.45, 1.47, 1.49 |

## Decision ledger

| Decision | Result | Evidence basis |
| --- | --- | --- |
| Ternary | Preserve for domain semantics; use binary buffers/ABI/WASI memory. No ternary-specific milestone before 1.50. | Current `README.md:23`, native/FFI contracts, workload evidence. |
| Generics | Defer; closed type-specific collection layouts first. | E01 plus absence in I03/I06 and no measured duplication. |
| Concurrency | External-first; language threads/atomics/async deferred. | I03, E09, E12, E13. |
| ARM64 | Post-1.50. | I14 and target-cost comparison. |
| Windows/macOS native | Post-1.50. | I03, I14, native x86-64 spec. |
| WASI | Select 1.49 after resource/build/interop. | E18-E20 and host-service direction. |
| Self-hosting | One bounded component in 1.50; Python oracle retained. | I02, I13, E16-E17. |
| Standard library | Small layered core in 1.44. | I16, E05, E01. |
| Packages | Local path graph and lockfile in 1.45; no registry. | I09, I15, E03-E05, E14-E15. |
| M1.38 Docker | Real certification deferred; no direct dependency claimed. | Prompt policy and I10. |

## Research limits

```text
EXTERNAL_RESEARCH_DOMAINS_MAX=12
REFERENCE_ECOSYSTEMS_USED=8
CANDIDATE_THEMES_EVALUATED=25
SELECTED_MILESTONES=12
ALTERNATE_ROADMAPS=1
P14_REOPENED=NO
```
