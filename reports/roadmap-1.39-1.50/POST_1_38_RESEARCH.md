# S3 Post-1.38 Evidence-Based Research

## Campaign identity

| Field | Value |
| --- | --- |
| Campaign | `S3-R139-R150` |
| Mode | Research and design only |
| Research base | `85541b782571c80d4857d013d1fb25b4997c1eb9` |
| Research branch | `research/post-1.38-roadmap-1.39-1.50-20260815` |
| Worktree | `S3-roadmap-139-150-research-20260815` |
| Production source changed | No |
| Test source changed | No |
| Remote writes | No |
| P14.3 started | No |
| M1.38 real Docker certification | Deferred |

The prior Linux certification SHA `46db2de...` was not treated as the base. The
actual checkout was inspected first. It is currently at the standalone JSMN
input-buffer commit `85541b7...`; `origin/experiment/jsmn-s3-20260810` points
to the same commit. The primary checkout was left untouched, including its two
untracked campaign files.

## Executive conclusion

S3 should focus first on making programs useful, with a dependency-ordered
language foundation. The current compiler is a credible bounded systems-language
prototype: static arrays, static text, nominal records/enums, modules, checked
IR, O0/O1, an emulator, and an experimental Linux x86-64 ELF backend are real.
The current 1.35-1.38 files are mostly explicit host-side contracts, not proof
that the source language has heap values, resource handles, packages, or Docker
execution.

The proposed order is:

1. owned byte buffers and deterministic dynamic text;
2. ordered user collections;
3. deterministic maps and sets;
4. explicit structured result/error flow;
5. scoped resources and capability enforcement;
6. a small versioned standard library;
7. deterministic build graph and lockfile;
8. a user-facing test runner;
9. richer C and Python buffer interop;
10. a capability-scoped network provider;
11. a WASI portability target;
12. one real self-hosted compiler/tooling component.

This is not Rust, Zig, C++, or Go parity. It is the smallest chain that turns
S3's current fixed-layout core into a language that can process runtime data,
return failures explicitly, use host resources, build multiple units, cross a
stable binary boundary, and progressively self-host. Generic syntax, language
threads/async, native ARM64, native Windows/macOS, a public registry, and a
complete self-hosted compiler remain deliberately deferred.

## A. Current S3 reality

### Capability matrix

| Capability | Classification | Current factual state | Evidence |
| --- | --- | --- | --- |
| Scalar types | Supported | `trit` and `tryte` are the published scalar domains; current internal contracts also model checked `i64` and finite `f64`. | `README.md:23`, `docs/milestone-1.32.md:6-27`, `bootstrap/s3/dynamic.py:15-54` |
| Composite types | Supported/partial | Fixed one-dimensional arrays, nominal acyclic records, and closed payload enums exist; recursive and open layouts do not. | `README.md:28,35-37`, `docs/structured-data-capabilities.md`, `docs/milestone-1.33.md:16-18` |
| Memory | Supported/partial | Frame-local fixed memory objects, `LOAD`/`STORE`, initialization checks, and bounded buffers exist; no heap or global memory exists in the source model. | `README.md:31-32,55`, `docs/architecture.md:212-224`, `docs/array-capabilities.md:84` |
| Ownership | Missing | Values are copied/fixed-layout; there is no source-level ownership or lifetime of a dynamic allocation. | `docs/ai-agent-guide.md:33-35`, `docs/self-hosting.md`, `spec/memory.md` |
| Borrowing | Missing | No pointer, reference, alias, or borrow checker semantics are exposed. | `README.md:31,55`, `spec/native-x86_64.md:142-143` |
| Dynamic data | Experimental/partial | Python contracts `DynamicValue` and `HostServiceRegistry` are closed scalar boundaries; they are not source-level dynamic containers. | `bootstrap/s3/dynamic.py:1-60`, `bootstrap/s3/host_services.py:30-50`, `docs/milestone-1.35.md:4-8` |
| Text | Partial | Static typed strings and literal-only compile-time concatenation exist; runtime construction, parsing, indexing, formatting, and broad text operations do not. | `README.md:29`, `docs/language-gaps.md:39`, `docs/ai-agent-guide.md:36` |
| Collections | Partial | Static arrays and fixed-capacity external JSMN buffers work; no user-visible vector, map, set, or resizing list exists. | `README.md:28`, `docs/array-capabilities.md:84`, `tests/test_external_jsmn_s3.py:134-190,253-258` |
| Functions | Supported | Functions, calls, recursion, loops, mutation, and aggregate internal lowering are present. | `README.md:24-27,102-107` |
| Modules | Supported/partial | Explicit multi-file modules, imports, exports, qualified calls, records, and enums exist; dependency packaging is absent. | `README.md:33-37`, `spec/modules.md`, `docs/milestone-1.37.md:8-10` |
| FFI | Experimental/partial | Scalar-only `trit`/`tryte`/`i64`/`f64` signatures with explicit integer/float ABI classes; no strings, buffers, headers, or public library distribution. | `bootstrap/s3/ffi.py:14-60`, `docs/milestone-1.34.md:4-10` |
| ABI | Supported/partial | Linux System V AMD64 native scalar and aggregate conventions are tested; only the Linux x86-64 native target is real. | `README.md:40-46`, `spec/native-x86_64.md:142-143` |
| Error model | Partial | Compiler diagnostics and payload enum foundations exist; source programs lack a general Result/error propagation model and exceptions are intentionally absent. | `README.md:96-107`, `docs/structured-data-capabilities.md`, `docs/ai-agent-guide.md:38` |
| Pattern matching | Supported | Exhaustive ternary `match` exists for statements and expressions; payload matching is bounded by current enum model. | `README.md:24`, `docs/structured-data-capabilities.md` |
| Genericity | Missing | No generics, templates, traits, interfaces, type parameters, or polymorphic collection syntax. | `README.md:136-140`, `docs/ai-agent-guide.md:38` |
| Metaprogramming | Partial/experimental | Constant folding and bounded frontend candidates exist; no user-facing comptime/code-generation contract. | `README.md:63-71,109-116`, `docs/ai-capabilities.json:94-104` |
| File I/O | Missing in source | Host services are injectable Python contracts; no source file handle or filesystem API. | `bootstrap/s3/host_services.py:30-50`, `docs/milestone-1.36.md:4-8`, `docs/language-gaps.md:63-67` |
| Process I/O | Missing in source | No source process spawn, pipes, or wait API. | `docs/milestone-1.36.md:4-8`, `docs/milestone-1.37.md:8-10` |
| Network I/O | Missing | No sockets or network provider. | `docs/ai-agent-guide.md:33-40`, repository source audit |
| Concurrency | Missing | No language threads, atomics, channels, async, or global mutable state. | `docs/ai-agent-guide.md:40`, `docs/structured-data-capabilities.md` |
| Threading | Deferred | OS threads can be hosted externally in a future provider; language-level thread semantics are not justified by current evidence. | `docs/ai-agent-guide.md:40`, WG14 atomics rationale |
| Atomics | Deferred | No memory-ordering or data-race model; adding it before resource/error foundations would be high risk. | `docs/ai-agent-guide.md:40`, `https://open-std.org/jtc1/sc22/wg14/www/docs/n1479.htm` |
| Async | Deferred | No task, poll, event-loop, or cancellation contract. | `docs/ai-agent-guide.md:40`, C++ coroutine design paper |
| Project model | Partial | `ProjectContainer` validates a named root and sorted unique units and computes a manifest hash. | `bootstrap/s3/project_container.py:17-52`, `docs/milestone-1.37.md:1-10` |
| Dependency model | Missing | No path dependency graph, lockfile, resolver, registry, or artifact cache. | `docs/milestone-1.37.md:8-10`, `spec/source-syntax-0.6.md:121` |
| Package model | Missing | No package distribution or registry contract. | `README.md:136-140`, `docs/language-gaps.md` |
| Container model | Experimental/partial | `DockerSpec` validates image, command, sorted environment, and timeout; no process/image/filesystem/network adapter is present on this HEAD. | `bootstrap/s3/s3_docker.py:17-40`, `docs/milestone-1.38.md:3-10` |
| Backends | Partial | Hosted emulator and Linux x86-64 assembly/ELF are present; no Windows, macOS, ARM64, or WASM backend. | `README.md:11-15,40-42`, `docs/arm64-feasibility.md:1-3` |
| Platforms | Partial | Hosted execution works across Python hosts; native execution is Linux x86-64 and CI-centered. | `docs/ai-agent-guide.md:91-92`, `spec/native-x86_64.md:142-143` |
| Self-hosting | Experimental | Bounded Assembly/text components are differential references only; Python remains the compiler and no S3 component accesses files or heap. | `docs/self-hosting.md`, `selfhost/README.md:9-23`, `tests/test_assembly_renderer_candidate_manifest.py` |
| Standard library | Missing | Runtime has Python standard-library implementation support, but the source language has no stable `core`, `text`, `io`, or `collections` library surface. | `pyproject.toml:12-16`, `docs/ai-agent-guide.md`, `README.md:136-140` |
| Tooling | Partial | CLI check/run/inspect/tokens/AST/IR/Assembly and JSON diagnostics exist; no LSP, formatter, package inspector, or integrated debugger. | `README.md:168-238`, `docs/ai-capabilities.json:88-104` |
| Debugging | Partial | Text/JSON diagnostics and native diagnostics include source/function/block context; no source-level debug info or debugger integration. | `README.md:224-235`, `docs/architecture.md`, LLVM source-debugging references |
| Testing | Supported for compiler, missing for users | The repository has extensive hosted/native/differential tests; S3 programs have no standard test blocks/runner. | `pyproject.toml:24-33`, `docs/language-gaps.md:44`, test inventory |
| Diagnostics | Supported/partial | Versioned hosted JSON diagnostics and native textual diagnostics exist; S3 code cannot yet construct rich runtime diagnostics. | `README.md:224-235`, `spec/diagnostics.md` |
| Serialization | Partial | IR JSON and Assembly formats are versioned and deterministic; source-level data serialization is absent. | `README.md:48-53`, `docs/assembly-program-data-contract.md` |
| Interoperability | Partial | Scalar ABI and external JSMN fixed-buffer differential example exist; Python/C buffer and library-level interop are absent. | `bootstrap/s3/ffi.py`, `tests/test_external_jsmn_s3.py`, Python buffer protocol |
| Security | Partial | Explicit injectable host-service registry prevents hidden access in the Python contract; there is no source capability token or runtime enforcement. | `bootstrap/s3/host_services.py:30-50`, `docs/milestone-1.36.md:4-8`, WASI capabilities |

### M1.32-M1.38 reality

The milestone documents are useful architectural boundaries, but they do not
all describe the same level of completion. M1.32-1.34 define numeric, slice,
and scalar FFI contracts. M1.35 defines a closed tagged scalar boundary; the
actual `DynamicValue` class confirms that scope. M1.36 adds a Python-side
injectable host registry, M1.37 a deterministic structural project manifest,
and M1.38 a deterministic Docker invocation value object. None of these three
last contracts alone gives S3 source programs filesystem handles, processes,
containers, or a package graph.

Real Docker certification remains `DEFERRED` by policy. This research does not
install, repair, or run Docker and no proposed milestone treats M1.38 as a
verified execution environment.

## B. Documentation and source-truth audit

| Finding | Impact | Resolution in this campaign |
| --- | --- | --- |
| `README.md` current development section stops at the 1.17-1.19 campaign and still calls dynamic text, filesystem access, and complete self-hosting unimplemented. | It is stale about later internal contracts, but still accurate about source-level dynamic text and self-hosting. | Record as `DOCUMENTATION_STALE`; do not edit. |
| `docs/language-gaps.md` predates the 1.32-1.38 structural contracts and calls modules/records/enums more unavailable than the current source. | Priority labels and examples cannot be read as current capability truth. | Record as `DOCUMENTATION_STALE` and use source/tests plus normative specs. |
| `docs/ai-capabilities.json`, `docs/ai-agent-guide.md`, and `spec/native-x86_64.md` agree that heap, pointers, dynamic arrays/text, generics, concurrency, and non-Linux native targets are absent. | These boundaries remain reliable for current source semantics. | Treat as current negative evidence. |
| M1.35-M1.38 documents describe structural contracts while implementation files are Python dataclasses/registries. | A milestone label can be mistaken for language support. | Classify as `IMPLEMENTATION_AHEAD_OF_DOCS` only for internal contracts; do not promote them to source capabilities. |
| The current checkout is a JSMN experiment branch, not the prior certification checkout. | Prior certification results cannot be copied into this base. | Use `85541b7...` as `RESEARCH_BASE_SHA`. |

No production or test file was repaired. The existing normative roadmap remains
unchanged. This report is a proposal, not an official roadmap promotion.

## C. Top ten current bottlenecks

1. Runtime text cannot be built, parsed, formatted, or safely passed from host input.
2. There is no user-level owned dynamic buffer or collection.
3. There is no deterministic map for symbol/configuration data.
4. Source programs cannot return structured recoverable errors from host operations.
5. Files, processes, and foreign resources have no source-level lifetime contract.
6. The project manifest is not a build/dependency graph and has no lockfile.
7. The source language has no small standard library for ordinary application work.
8. Users have no S3-native test runner or reproducible program-test convention.
9. FFI stops at scalar calls; useful buffer and C/Python library boundaries are absent.
10. Only Linux x86-64 is a native target, and there is no portable host capability target.

Generics, language-level concurrency, and additional native backends are not
ranked above these bottlenecks because current workloads are blocked earlier by
data representation, ownership, error, resource, and build contracts.

## D. Workload stress test

| Workload | What works today | Blocking gap | First unlocking milestones |
| --- | --- | --- | --- |
| A. Scientific numerical CLI | Fixed numerical loops and bounded arrays; checked `i64`/`f64` contracts. | Runtime input, large resizable buffers, error reporting, library interop. | 1.39, 1.40, 1.42, 1.47. |
| B. Native library callable from Python/C | Scalar Linux ABI and fixed-buffer experiment. | Stable header/layout, byte buffers, ownership, status/error boundary. | 1.39, 1.42, 1.43, 1.47. |
| C. File-processing utility | Compile-time fixtures and fixed arrays only. | Text, filesystem handles, resource cleanup, standard I/O. | 1.39, 1.42-1.44. |
| D. Small network service | No source socket API. | Socket capability, buffers/text, errors, lifecycle, hosted fakes. | 1.39, 1.42-1.44, 1.48. |
| E. Compiler/tooling component | Bounded Assembly renderer/JSMN-style fixed buffer can be differential-tested. | Runtime text, collections, build/test conventions, richer diagnostics. | 1.39-1.46, then 1.50. |
| F. Large data/buffer processing | Fixed arrays and bounded external input can work. | Owned growth, streaming, predictable memory failure, buffer interop. | 1.39, 1.40, 1.43, 1.47. |
| G. Containerized service | Docker invocation structure only. | Application I/O/network/library contracts and verified container runtime. | 1.39-1.48; M1.38 Docker certification remains separate/deferred. |
| H. Portable native application | Hosted emulator and Linux x86-64 native only. | Target abstraction and portable host API; WASI backend. | 1.45, 1.47, 1.49. |

## E. Scientific and ternary analysis

The scientific workload favors ordinary contiguous binary buffers, `i64`/`f64`,
stable C/Python interop, deterministic batch pipelines, and eventual external
parallelism. Balanced ternary remains valuable for exact S3 domains, bounded
state machines, and domain-specific decision/state encodings. It is not a good
reason to encode arbitrary byte buffers, UTF-8, C ABI slots, or WASI linear
memory as trits.

`TERNARY_FUTURE_OPPORTUNITY=bounded domain-specific arithmetic and state
encoding; NO_PRE_1_50_MILESTONE_JUSTIFIED`. No new evidence justifies reopening
the P12 compact-state performance line.

## F. External research findings

The primary-source comparison was capped at eight reference ecosystems or
standards families: Rust, Zig, C/POSIX, C++, LLVM, Python C API, Go modules,
and WebAssembly/WASI.

* Rust's generics and traits solve reuse and behavioral constraints, but its
  ownership/lifetime model is a large semantic commitment. S3 should first
  ship specialized deterministic collections and explicit resource contracts;
  generic syntax is not a prerequisite for the first useful applications.
* Zig demonstrates that explicit allocators and a dependency-free build system
  can keep resource policy visible. That supports an explicit buffer/resource
  boundary, not implicit garbage collection.
* C/POSIX makes file descriptors and sockets explicit resources and exposes the
  error/close/nonblocking surface that S3 must model before source I/O.
* C++ ranges and coroutines show the value and semantic cost of abstraction over
  iteration and asynchronous execution. S3 should not adopt either as a syntax
  milestone before simpler vectors and provider APIs work.
* LLVM's target-independent IR and source-debugging material reinforce a
  separate target contract and a later source-location/debug information effort;
  they do not make a second backend cheap.
* Python's buffer protocol and Stable ABI provide a concrete interop target:
  borrowed contiguous bytes and a stable limited ABI are more valuable than a
  broad Python object binding.
* Go modules and Cargo workspaces/resolvers both show why a project manifest
  must become a deterministic graph with lock information before a registry is
  attempted.
* WebAssembly is a portable computation core while WASI and the Component Model
  layer host capabilities and canonical boundary conversions. This fits S3's
  explicit host-service direction better than pretending Docker is a language
  portability target.

Primary source ledger and URLs are in `EVIDENCE_LEDGER.md`.

## G. Platform strategy

| Target | Decision | Reason |
| --- | --- | --- |
| Linux x86-64 | Keep first-class | Existing native backend, ABI evidence, and CI make it the closure target for every native milestone. |
| Linux ARM64 | Post-1.50 | The existing feasibility study requires a new emitter/runtime/toolchain/CI path; no current workload requires it before data/resource foundations. |
| Windows x86-64 | Post-1.50 | Developer-host convenience is not sufficient justification for a second native ABI and toolchain while source capabilities remain incomplete. Hosted tests remain useful on Windows. |
| macOS ARM64 | Post-1.50 | It combines a new target with a new host/toolchain/CI policy and has lower immediate leverage than WASI. |
| WebAssembly/WASI | Select M1.49 | A portable core plus explicit host capabilities is a bounded strategic expansion after the source and build contracts exist. |

## H. Generics, concurrency, security, and self-hosting decisions

* `GENERICS_DECISION=POST_1_50 unless duplicate collection APIs become a measured
  maintenance blocker`. M1.40 may use compiler-generated type-specific layouts,
  but it does not define open user generic syntax. Revisit after at least two
  real libraries demonstrate the same abstraction boundary.
* `CONCURRENCY_DECISION=external-first; language threads/atomics/async post-1.50`.
  M1.48 can use a provider with deterministic hosted fakes and blocking or
  explicitly nonblocking socket operations, without promising language-level
  tasks or memory ordering.
* `SECURITY_DECISION=explicit declarative capabilities plus provider enforcement`.
  M1.43 defines the source-visible capability/resource boundary; M1.48 and M1.49
  apply it to network and WASI hosts.
* `SELF_HOSTING_DECISION=incremental component migration in M1.50`, not a full
  compiler rewrite. The first target is the bounded Assembly/diagnostic tool
  path because its inputs, outputs, and differential oracle already exist.
* `STDLIB_DECISION=small layered core`, with deterministic `core`, `text`,
  `collections`, `io`, and `host` modules. No monolithic library.
* `PACKAGE_MANAGEMENT_DECISION=local path dependencies plus content-hashed
  lockfile first`; no public registry before reproducible local graphs work.

## I. Primary roadmap rationale

The order follows the actual dependency chain:

```text
owned bytes/text
    -> vectors
    -> deterministic maps
    -> explicit result/errors
    -> scoped resources/capabilities
    -> standard library
    -> build graph/lockfile
    -> user test runner
    -> C/Python buffer ABI
    -> network provider
    -> WASI target
    -> self-hosted component
```

This chain makes an ordinary file utility possible before a network service,
and makes a real self-hosted component depend on the same facilities ordinary
programs need. It also keeps binary hardware conventional: trit/tryte stay
first-class where their semantics matter, while buffers, text encoding, ABI
slots, and WASI memory use ordinary binary representations.

## J. Alternate strategy

`ALTERNATIVE_ROADMAP=PORTABILITY_FIRST`: place target abstraction, WASI, and
expanded C ABI in 1.39-1.41, then add a reduced text/buffer layer, provider
resources, and collections before self-hosting. This would produce a portable
demonstration earlier, but it leaves the portable program unable to process
runtime text or recover from ordinary I/O failures. The primary roadmap wins
because it removes the blockers common to six of the eight workloads before
paying for a second backend.

## K. What S3 can plausibly build after 1.50

With all twelve milestones complete, S3 should plausibly build a deterministic
file-processing CLI, a numerical batch/native component, a small capability-
scoped network service, and a portable core running through a WASI provider. It
should also compile and test one bounded Assembly or diagnostic component from
S3, while Python remains the reference compiler. It should not yet claim a
complete self-hosted compiler, language-level async/threading, native ARM64 or
Windows/macOS, a public registry, or general Rust-like generic libraries.

## L. Next implementation recommendation

`NEXT_IMPLEMENTATION_MILESTONE=1.39 - Owned Byte Buffers and Deterministic
Dynamic Text`.

It has the highest combined application and self-hosting leverage, is a clear
semantic boundary, and is a prerequisite for collections, errors in readable
form, I/O, FFI buffers, networking, WASI strings, and a self-hosted renderer.
The first campaign must define representation, ownership, failure, encoding,
and O0/O1/native/differential gates before adding convenience APIs.

## Control fields

```text
ROADMAP_RESEARCH_STATUS=COMPLETE_LOCAL_RESEARCH_ONLY
RESEARCH_BASE_SHA=85541b782571c80d4857d013d1fb25b4997c1eb9
PRODUCTION_SOURCE_CHANGED=NO
TEST_SOURCE_CHANGED=NO
M138_DOCKER_CERTIFICATION=DEFERRED
REMOTE_WRITE_EXECUTED=NO
P14_3_STARTED=NO
DOCKER_INSTALLED=NO
SHUTDOWN_EXECUTED=NO
REBOOT_EXECUTED=NO
```
