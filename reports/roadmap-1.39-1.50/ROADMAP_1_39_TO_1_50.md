# Proposed Roadmap: S3 Milestones 1.39-1.50

This is a local research proposal. It does not modify `docs/roadmap.md`,
compiler source, runtime source, tests, or the public package.

## Phase A: runtime values and deterministic control

### MILESTONE=1.39

**TITLE=Owned Byte Buffers and Deterministic Dynamic Text**

**PROBLEM:** S3 can represent static text and fixed arrays, but cannot process
runtime file/network input, construct diagnostics, or format ordinary values.

**USER_VALUE:** File filters, numerical CLI input, diagnostics, and the first
larger self-hosted renderer become possible.

**CURRENT_S3_GAP:** No heap/owned buffer, runtime text, encoding validation,
growth failure, or source-level text API.

**INTERNAL_EVIDENCE:** `README.md:29-31,55`, `docs/ai-agent-guide.md:33-36`,
`docs/language-gaps.md:39`, and the fixed-capacity JSMN fixture in
`tests/test_external_jsmn_s3.py:134-190`.

**EXTERNAL_EVIDENCE:** Python buffer protocol for explicit contiguous storage;
Zig allocator documentation for visible allocation policy.

**WHY_NOW:** Every later application capability needs bytes, text, and explicit
failure behavior.

**WHY_NOT_EARLIER:** M1.32-1.38 established numeric, host, project, and
structural boundaries first.

**WHY_NOT_LATER:** Deferring text would make collections, I/O, FFI, networking,
WASI, and self-hosting mostly demonstrators without useful input/output.

**DEPENDENCIES:** Current fixed-layout values, bounds, initialization checks,
M1.35 scalar boundary as historical design input.

**DELIVERABLES:** Owned byte buffer with explicit capacity/length and failure;
UTF-8 validation boundary; append/concat/slice/search; integer parsing and
deterministic integer formatting; explicit copy/borrow rules for host input.

**NON_GOALS:** Unicode grapheme segmentation, implicit conversions, GC,
pointer syntax, general borrow checking, float formatting policy, or text
exceptions.

**ACCEPTANCE_GATES:** valid/invalid UTF-8 cases; overflow and capacity errors;
O0/O1 equality; hosted/native differential cases; deterministic byte/text
serialization; no out-of-bounds read/write; Linux x86-64 native round trips.

**HOSTED_TESTS:** buffer ownership, text operations, error paths, limits.

**NATIVE_TESTS:** binary buffer layout and native text round trips.

**DIFFERENTIAL_TESTS:** Python oracle versus hosted and native fixed corpus.

**PLATFORM_REQUIREMENTS:** Linux x86-64 native; hosted Windows/macOS/Linux.

**DOCUMENTATION_REQUIRED:** memory/text contract, encoding policy, failure
codes, and source examples.

**RISKS:** hidden allocation semantics, representation leaks, and accidental
Unicode promise.

**ESTIMATED_COMPLEXITY=HIGH**

**UNLOCKS:** 1.40-1.50 application data paths.

### MILESTONE=1.40

**TITLE=Deterministic Ordered User Collections**

**PROBLEM:** Fixed arrays cannot grow and there is no reusable user-level vector
or byte collection.

**USER_VALUE:** Batch processing, token lists, numerical buffers, and compiler
symbol sequences can be written without hand-unrolled fixed storage.

**CURRENT_S3_GAP:** `docs/array-capabilities.md:84` explicitly records fixed
size only; current JSMN uses a fixed input and token capacity.

**INTERNAL_EVIDENCE:** `README.md:28`, `tests/test_external_jsmn_s3.py:13-18`.

**EXTERNAL_EVIDENCE:** C++ range requirements and Rust collection design show
why ordered iteration and ownership must be explicit.

**WHY_NOW:** M1.39 supplies bytes and ownership; maps and the standard library
need one deterministic collection substrate.

**WHY_NOT_EARLIER:** A vector before an owned buffer would hide allocation and
failure rules.

**WHY_NOT_LATER:** Compiler/tooling and scientific workloads need collections
before build and self-hosting work.

**DEPENDENCIES:** 1.39.

**DELIVERABLES:** ordered vector over closed element layouts; byte buffer view;
length/capacity/reserve/push/pop/index; deterministic iteration; defined
allocation failure; type-specific generated layouts without public generic
syntax.

**NON_GOALS:** deque, hash table, implicit sharing, concurrent mutation, or
general generic parameters.

**ACCEPTANCE_GATES:** growth and failure boundaries; stable iteration; bounds
diagnostics; O0/O1/native/differential equivalence; leak/cleanup tests.

**HOSTED_TESTS:** randomized fixed-seed vector operations.

**NATIVE_TESTS:** large contiguous buffer operations and numeric batches.

**DIFFERENTIAL_TESTS:** reference model against hosted and native sequences.

**PLATFORM_REQUIREMENTS:** Linux x86-64 native; hosted all supported hosts.

**DOCUMENTATION_REQUIRED:** collection layout, ownership, invalidation, limits.

**RISKS:** capacity arithmetic and accidental iterator aliasing.

**ESTIMATED_COMPLEXITY=HIGH**

**UNLOCKS:** 1.41, 1.44, 1.46, 1.50.

### MILESTONE=1.41

**TITLE=Deterministic Maps and Sets**

**PROBLEM:** Symbol tables, configuration, structured input, and diagnostics
need lookup; vectors alone make lookup code and ordering fragile.

**USER_VALUE:** Deterministic configuration and compiler/tooling indexes.

**CURRENT_S3_GAP:** No map/set source type, stable hashing policy, or structural
lookup API.

**INTERNAL_EVIDENCE:** `docs/structured-data-capabilities.md` excludes dynamic
type/reflection and `docs/language-gaps.md` lists maps as unavailable.

**EXTERNAL_EVIDENCE:** Go module graph and Cargo resolver evidence the value of
stable identity and reproducible graph decisions; C++ range ordering informs
iteration semantics.

**WHY_NOW:** 1.40 provides storage and 1.42 needs deterministic error/context
lookup.

**WHY_NOT_EARLIER:** A map before ordered collection and text keys would either
be a special case or introduce nondeterminism.

**WHY_NOT_LATER:** Self-hosted symbol/diagnostic tools need lookup before 1.50.

**DEPENDENCIES:** 1.39, 1.40.

**DELIVERABLES:** ordered map with explicit key equality/order; set derived from
the same contract; deterministic serialization; optional stable hash only with
specified seed/collision/iteration policy.

**NON_GOALS:** randomized hash tables, reflection, open records, or concurrent
maps.

**ACCEPTANCE_GATES:** insertion/replacement/deletion/lookup; duplicate policy;
stable iteration and serialization; fixed-seed differential corpus; memory
limits and native equivalence.

**HOSTED_TESTS:** map model/property tests.

**NATIVE_TESTS:** representative symbol/configuration tables.

**DIFFERENTIAL_TESTS:** sorted operation traces against a reference model.

**PLATFORM_REQUIREMENTS:** Linux x86-64 native; hosted all supported hosts.

**DOCUMENTATION_REQUIRED:** ordering, key domain, hashing, limits.

**RISKS:** hidden nondeterminism and cost of deep key comparison.

**ESTIMATED_COMPLEXITY=HIGH**

**UNLOCKS:** 1.42, 1.44, 1.45, 1.50.

### MILESTONE=1.42

**TITLE=Explicit Structured Result and Error Flow**

**PROBLEM:** Source code has no uniform recoverable error contract for buffers,
files, FFI, and host services.

**USER_VALUE:** Programs can report invalid input, capacity, I/O, and foreign
errors without exceptions or ambiguous sentinel values.

**CURRENT_S3_GAP:** Payload enums exist, but source has no general Result-like
propagation; `README.md:96-107` explicitly excludes generic result and `?`.

**INTERNAL_EVIDENCE:** `docs/structured-data-capabilities.md`, current payload
enum docs, and `bootstrap/s3/host_services.py:43-50`.

**EXTERNAL_EVIDENCE:** Rust's official error-handling model demonstrates the
recoverable-result versus unrecoverable-panic distinction without requiring
S3 to copy generic syntax.

**WHY_NOW:** Every host/resource API needs one explicit failure vocabulary.

**WHY_NOT_EARLIER:** Error payload design depends on records/enums and dynamic
text/collections.

**WHY_NOT_LATER:** Delaying it would make I/O and FFI APIs invent incompatible
status conventions.

**DEPENDENCIES:** 1.39-1.41 and existing payload enums.

**DELIVERABLES:** closed named success/error result contract; explicit match and
propagation form or equivalent checked return rule; stable error codes/payloads;
panic/trap boundary; no exceptions or unwinding.

**NON_GOALS:** generic `Result<T,E>` syntax, exceptions, implicit propagation,
or dynamic reflection.

**ACCEPTANCE_GATES:** valid success/error paths; rejected unchecked use;
specific diagnostics; O0/O1/native/differential equivalence; nested error
context and deterministic serialization.

**HOSTED_TESTS:** error construction, matching, propagation, trap distinction.

**NATIVE_TESTS:** status/error ABI values and return paths.

**DIFFERENTIAL_TESTS:** reference error traces across hosted/native execution.

**PLATFORM_REQUIREMENTS:** Linux x86-64 native; hosted all supported hosts.

**DOCUMENTATION_REQUIRED:** error taxonomy and propagation rules.

**RISKS:** hidden control-flow edges and error payload ABI growth.

**ESTIMATED_COMPLEXITY=HIGH**

**UNLOCKS:** 1.43-1.50.

## Phase B: host resources and application workflow

### MILESTONE=1.43

**TITLE=Scoped Host Resources and Capability Enforcement**

**PROBLEM:** Files, processes, sockets, and foreign buffers have no source
handle, cleanup, or capability policy.

**USER_VALUE:** Resource-using applications can close deterministically and
cannot silently acquire undeclared host access.

**CURRENT_S3_GAP:** M1.36 is an injectable Python registry with scalar values;
it has no source-level handle or lifetime.

**INTERNAL_EVIDENCE:** `bootstrap/s3/host_services.py:30-50`,
`docs/milestone-1.36.md`, `docs/ai-agent-guide.md:33-40`.

**EXTERNAL_EVIDENCE:** POSIX `open` and socket specifications make descriptors,
flags, errors, and close behavior explicit; WASI capabilities reinforce
declarative host authority.

**WHY_NOW:** Text, collections, and errors make handles usable and reportable.

**WHY_NOT_EARLIER:** A resource syntax before error and ownership rules would
leak cleanup policy into every later API.

**WHY_NOT_LATER:** File, FFI, networking, and WASI cannot be credible without
this boundary.

**DEPENDENCIES:** 1.39, 1.42, M1.36 contract.

**DELIVERABLES:** opaque typed handles; explicit capability tokens; deterministic
close and scope cleanup; provider registration; use-after-close rejection;
resource-limit and failure errors.

**NON_GOALS:** garbage collection, full Rust borrow checking, implicit RAII for
all values, threads, or unrestricted OS access.

**ACCEPTANCE_GATES:** open/use/close lifecycle; double-close and leak tests;
capability denial; deterministic cleanup on error; hosted fake provider and
Linux native provider equivalence.

**HOSTED_TESTS:** fake file/process/handle providers and fault injection.

**NATIVE_TESTS:** Linux descriptor lifecycle and bounded process fixture.

**DIFFERENTIAL_TESTS:** provider trace equivalence, including failures.

**PLATFORM_REQUIREMENTS:** Linux x86-64 native; hosted Windows/macOS/Linux.

**DOCUMENTATION_REQUIRED:** capability manifest, lifetime, close, limits.

**RISKS:** cleanup on all control-flow exits and capability confusion.

**ESTIMATED_COMPLEXITY=VERY_HIGH**

**UNLOCKS:** 1.44, 1.47, 1.48, 1.49.

### MILESTONE=1.44

**TITLE=Small Layered Standard Library Core**

**PROBLEM:** Language facilities remain scattered contracts; programmers have
no stable source modules for common operations.

**USER_VALUE:** Programs can import a predictable `core`, `text`,
`collections`, `io`, and `host` surface instead of rebuilding helpers.

**CURRENT_S3_GAP:** No source-level standard library; Python stdlib is only the
bootstrap implementation.

**INTERNAL_EVIDENCE:** `pyproject.toml:12-16`, `docs/ai-agent-guide.md`,
`README.md:136-140`.

**EXTERNAL_EVIDENCE:** Zig's explicit build/allocator approach and Rust's
layered standard APIs show the value of a coherent small core without requiring
one monolithic library.

**WHY_NOW:** 1.39-1.43 have enough contracts to stabilize APIs.

**WHY_NOT_EARLIER:** A library before ownership/errors/resources would freeze
the wrong conventions.

**WHY_NOT_LATER:** Every subsequent build, test, FFI, network, and self-hosting
campaign needs reusable source modules.

**DEPENDENCIES:** 1.39-1.43.

**DELIVERABLES:** versioned module layout; text/collection helpers; explicit
`io` and `host` wrappers; capability declarations; compatibility policy.

**NON_GOALS:** giant batteries-included library, package registry, Unicode
locale database, or C++/Python object wrappers.

**ACCEPTANCE_GATES:** cross-module imports; deterministic API fixtures;
hosted/native behavior; documentation examples; no hidden capabilities.

**HOSTED_TESTS:** library module contract tests.

**NATIVE_TESTS:** representative CLI and numerical examples.

**DIFFERENTIAL_TESTS:** standard-library oracle for text/collection/io results.

**PLATFORM_REQUIREMENTS:** Linux x86-64 native; hosted all supported hosts.

**DOCUMENTATION_REQUIRED:** module API and versioning policy.

**RISKS:** scope expansion and accidental platform-specific APIs.

**ESTIMATED_COMPLEXITY=HIGH**

**UNLOCKS:** 1.45-1.50.

### MILESTONE=1.45

**TITLE=Deterministic Build Graph and Local Lockfile**

**PROBLEM:** The project container is a sorted manifest, not a build graph;
multi-library builds and reproducible dependencies are missing.

**USER_VALUE:** A project can build several S3 units and local libraries with a
stable dependency closure on another machine.

**CURRENT_S3_GAP:** `ProjectContainer` hashes unit/source names but does not
resolve, lock, or build dependencies.

**INTERNAL_EVIDENCE:** `bootstrap/s3/project_container.py:31-52`,
`docs/milestone-1.37.md:8-10`, `spec/source-syntax-0.6.md:121`.

**EXTERNAL_EVIDENCE:** Cargo workspaces/resolver and Go modules provide primary
examples of graph identity, lock/reproducibility, and version selection.

**WHY_NOW:** Text, errors, resources, and the standard library define the
artifacts a build graph must carry.

**WHY_NOT_EARLIER:** A resolver before stable module/library boundaries would
lock unstable interfaces.

**WHY_NOT_LATER:** Test, interop, and self-hosting need repeatable multi-unit
builds.

**DEPENDENCIES:** M1.37, 1.44.

**DELIVERABLES:** `s3.toml` graph; local path dependencies; content-hashed
lockfile; target/profile records; deterministic topological build; artifact
cache identity; explicit foreign-library declarations.

**NON_GOALS:** public registry, semantic version ecosystem, remote Git fetch, or
incremental compiler internals.

**ACCEPTANCE_GATES:** same graph produces same lock/hash; missing or cyclic
dependency diagnostics; isolated build; target-profile rejection; reproducible
artifact manifest.

**HOSTED_TESTS:** graph/resolver/lockfile model tests.

**NATIVE_TESTS:** multi-unit Linux executable and static library fixture.

**DIFFERENTIAL_TESTS:** independent resolver/reference manifest comparison.

**PLATFORM_REQUIREMENTS:** Linux x86-64 native; hosted all supported hosts.

**DOCUMENTATION_REQUIRED:** project file, lockfile, target/profile semantics.

**RISKS:** graph identity, cache invalidation, and accidental package-manager
scope.

**ESTIMATED_COMPLEXITY=HIGH**

**UNLOCKS:** 1.46-1.50.

### MILESTONE=1.46

**TITLE=User-Facing Reproducible S3 Test Runner**

**PROBLEM:** Compiler tests are strong, but S3 programs have no standard test
convention or command.

**USER_VALUE:** Application authors can run deterministic unit/program tests and
get failures without maintaining a Python harness.

**CURRENT_S3_GAP:** `docs/language-gaps.md:44` identifies the missing dedicated
S3 component/program test harness; `pyproject.toml` only configures pytest for
the compiler repository.

**EXTERNAL_EVIDENCE:** Cargo's workspace/test model and Zig's build/test task
model show a test runner can be a build contract rather than language magic.

**WHY_NOW:** Stable text, errors, stdlib, and build graph make test results
expressible and reproducible.

**WHY_NOT_EARLIER:** Earlier tests would require fixed fixtures and Python glue.

**WHY_NOT_LATER:** The test runner is needed to validate all later application
and self-hosting work without capability substitution.

**DEPENDENCIES:** 1.42, 1.44, 1.45.

**DELIVERABLES:** convention-based or explicit test entrypoints; `s3 test`;
fixed seed/timeout/output schema; hosted/native modes; capability sandbox;
machine-readable result report.

**NON_GOALS:** full property-testing language, debugger, benchmark framework,
or replacing compiler CI.

**ACCEPTANCE_GATES:** pass/fail/skip semantics; deterministic ordering; timeout
and resource failure; O0/O1 and native differential; isolated capability tests.

**HOSTED_TESTS:** runner protocol, reports, fault injection.

**NATIVE_TESTS:** Linux executable test fixtures.

**DIFFERENTIAL_TESTS:** same test corpus in hosted and native modes.

**PLATFORM_REQUIREMENTS:** Linux x86-64 native; hosted all supported hosts.

**DOCUMENTATION_REQUIRED:** test naming, fixtures, output schema, isolation.

**RISKS:** test behavior becoming a second language and nondeterministic output.

**ESTIMATED_COMPLEXITY=MEDIUM**

**UNLOCKS:** reliable 1.47-1.50 closure.

## Phase C: interop and host reach

### MILESTONE=1.47

**TITLE=Richer C ABI and Python Buffer Interop**

**PROBLEM:** Scalar-only FFI cannot expose useful arrays, bytes, text, or a
stable native library to C/Python.

**USER_VALUE:** Numerical, image/data, and compiler components can be called by
existing native/Python applications without copying every scalar manually.

**CURRENT_S3_GAP:** `FFISignature` rejects non-scalar parameters and results;
there is no header generation or ownership/status contract.

**INTERNAL_EVIDENCE:** `bootstrap/s3/ffi.py:30-60`, `docs/milestone-1.34.md:4-10`,
`tests/test_external_jsmn_s3.py`.

**EXTERNAL_EVIDENCE:** Python Stable ABI and buffer protocol provide a bounded
foreign boundary based on stable layout and explicit buffer release.

**WHY_NOW:** 1.39-1.44 define bytes/text, errors, and resource lifetime.

**WHY_NOT_EARLIER:** Scalar FFI is the correct narrow 1.34 boundary; richer
buffers without ownership would be unsafe.

**WHY_NOT_LATER:** Scientific/native library workloads are otherwise blocked.

**DEPENDENCIES:** 1.39, 1.42, 1.43, 1.44, 1.46.

**DELIVERABLES:** C header emission; bytes/slice/text views; status/error
convention; copy versus borrowed lifetime; Python buffer adapter; deterministic
ABI manifest; Linux static/shared library fixture.

**NON_GOALS:** C++ ABI, arbitrary Python object API, callbacks across threads,
variadic functions, or implicit global runtime.

**ACCEPTANCE_GATES:** C compile/link/round trip; Python buffer read-only and
read-write cases; release/use-after-release rejection; mixed scalar/buffer ABI;
hosted/native differential.

**HOSTED_TESTS:** ABI manifest, buffer lifetime, foreign failure tests.

**NATIVE_TESTS:** C and Python integration on Linux x86-64.

**DIFFERENTIAL_TESTS:** reference byte/status vectors across all adapters.

**PLATFORM_REQUIREMENTS:** Linux x86-64 native; hosted adapters elsewhere only
where explicitly available.

**DOCUMENTATION_REQUIRED:** header, layout, ownership, status, and versioning.

**RISKS:** ABI drift, lifetime bugs, and platform-specific calling conventions.

**ESTIMATED_COMPLEXITY=VERY_HIGH**

**UNLOCKS:** scientific/native library workload and 1.48-1.50 adapters.

### MILESTONE=1.48

**TITLE=Capability-Scoped Network Provider**

**PROBLEM:** A small service cannot accept or send data because S3 has no socket
or network host capability.

**USER_VALUE:** Deterministic local network services and clients become possible
without making networking an implicit language primitive.

**CURRENT_S3_GAP:** No sockets, handles, network errors, or source capability
declarations exist.

**INTERNAL_EVIDENCE:** `docs/ai-agent-guide.md:33-40`, `bootstrap/s3/host_services.py`,
`docs/milestone-1.36.md`.

**EXTERNAL_EVIDENCE:** POSIX socket definitions specify descriptor, byte-stream,
nonblocking, and close behavior; WASI capabilities support explicit host access.

**WHY_NOW:** 1.39 text, 1.42 errors, 1.43 resources, and 1.44 host modules
provide the correct boundary.

**WHY_NOT_EARLIER:** Network APIs before resource/error contracts create hidden
cleanup and status semantics.

**WHY_NOT_LATER:** Networked workload is a key product test for the capability
model and should precede the portable host target.

**DEPENDENCIES:** 1.39, 1.42-1.44, 1.46, optionally 1.47 buffer views.

**DELIVERABLES:** explicit client/listener capability; stream handle; bounded
read/write; timeout/nonblocking choice; deterministic hosted fake; Linux
loopback provider; text-independent byte protocol core.

**NON_GOALS:** language threads, async syntax, TLS, HTTP framework, UDP policy,
or unrestricted remote-network tests.

**ACCEPTANCE_GATES:** loopback round trip; denial without capability; EOF,
timeout, partial read/write, close; hosted fake/native trace equivalence;
resource-limit and deterministic test runner output.

**HOSTED_TESTS:** fake socket state machine and fault corpus.

**NATIVE_TESTS:** Linux loopback client/server fixture.

**DIFFERENTIAL_TESTS:** protocol bytes and error traces against the fake oracle.

**PLATFORM_REQUIREMENTS:** Linux x86-64 native; hosted provider abstraction.

**DOCUMENTATION_REQUIRED:** capability names, blocking policy, limits, errors.

**RISKS:** timing nondeterminism, leaked descriptors, and scope creep into async.

**ESTIMATED_COMPLEXITY=VERY_HIGH**

**UNLOCKS:** small network services and M1.49 host mapping.

### MILESTONE=1.49

**TITLE=Portable WASI Host and Target Contract**

**PROBLEM:** Native execution is Linux x86-64 only; hosted portability does not
produce a portable S3 artifact with explicit host services.

**USER_VALUE:** A bounded S3 core can run in a browser/server sandbox or another
WASI host without claiming a second native OS ABI.

**CURRENT_S3_GAP:** `docs/arm64-feasibility.md` and `spec/native-x86_64.md`
confirm one native target; no WASM target/provider exists.

**INTERNAL_EVIDENCE:** typed IR, explicit backend registry, host-service
registry, and deterministic project/build contracts.

**EXTERNAL_EVIDENCE:** WebAssembly core specs, WASI capability design, and the
Component Model canonical ABI explain the computation/host separation and
boundary lifting/lowering needed here.

**WHY_NOW:** Text, resources, capabilities, build, test, and interop are defined.

**WHY_NOT_EARLIER:** A WASI backend before dynamic values and resource errors
would only run fixed examples.

**WHY_NOT_LATER:** Portability is a strategic product test before self-hosting.

**DEPENDENCIES:** 1.39, 1.42-1.46, 1.47, 1.48.

**DELIVERABLES:** target triple and capability mapping; bounded WASM/WASI
backend/provider; canonical byte/text/error boundary; reproducible artifact;
hosted fake and one real WASI runtime matrix.

**NON_GOALS:** browser UI, component registry, arbitrary WASI extensions,
Docker certification, ARM64, Windows, or native macOS.

**ACCEPTANCE_GATES:** compile/run portable fixture; deterministic module bytes
under pinned toolchain; file/clock or network capability denial/allow; hosted
versus WASI result equivalence; resource and timeout tests.

**HOSTED_TESTS:** target/capability manifest and fake provider tests.

**NATIVE_TESTS:** Linux-hosted WASI runtime execution, not a second native S3 ABI.

**DIFFERENTIAL_TESTS:** Linux native versus WASI byte/result corpus.

**PLATFORM_REQUIREMENTS:** Linux x86-64 build/CI with pinned WASM/WASI runtime.

**DOCUMENTATION_REQUIRED:** target support matrix and capability restrictions.

**RISKS:** backend mapping, runtime version drift, and accidental WASI surface.

**ESTIMATED_COMPLEXITY=VERY_HIGH**

**UNLOCKS:** portable application core and 1.50 cross-target self-hosting proof.

## Phase D: self-hosting closure

### MILESTONE=1.50

**TITLE=Incremental Self-Hosted Assembly and Diagnostic Component**

**PROBLEM:** Python remains the only compiler of record; bounded S3 components
are differential references and cannot yet form a useful build/test artifact.

**USER_VALUE:** S3 users gain a real example of a larger maintainable tool, and
the project validates its own text, collections, errors, build, tests, and
interop contracts on an actual component.

**CURRENT_S3_GAP:** `docs/self-hosting.md` and `selfhost/README.md` explicitly
keep Python as reference and exclude filesystem, heap, pointers, and dynamic text.

**EXTERNAL_EVIDENCE:** LLVM's IR/source-debugging split supports keeping a
reference pipeline while incrementally migrating a component; Rust and Zig
demonstrate the value of a compiler/build toolchain testing itself, without
requiring S3 to migrate the whole compiler at once.

**WHY_NOW:** All practical program foundations and at least one portable target
exist.

**WHY_NOT_EARLIER:** Earlier self-hosting would be constrained by fixed buffers,
Python-only tests, and absent build/resource contracts.

**WHY_NOT_LATER:** A real component is the validation outcome of the entire
1.39-1.49 chain and exposes the next architectural gaps.

**DEPENDENCIES:** 1.39-1.49.

**DELIVERABLES:** S3 Assembly/diagnostic formatter component; source spans and
deterministic serialized output required by that component; build/test entry;
Python differential oracle retained; Linux native and WASI artifact where
feasible.

**NON_GOALS:** full parser migration, self-hosted optimizer/backend, compiler
bootstrap replacement, generics, debugger, or Docker closure.

**ACCEPTANCE_GATES:** component builds from a clean lockfile; hosted/native
output matches Python oracle; O0/O1 equivalence; user test runner passes;
deterministic serialized output; one portable target run; no hidden host access.

**HOSTED_TESTS:** component unit and golden-free semantic differential tests.

**NATIVE_TESTS:** Linux x86-64 component execution.

**DIFFERENTIAL_TESTS:** Python reference, S3 hosted, native, and WASI output
matrix for fixed source/IR/Assembly cases.

**PLATFORM_REQUIREMENTS:** Linux x86-64 required; WASI proof required if M1.49
runtime is stable; other native platforms remain out.

**DOCUMENTATION_REQUIRED:** component boundary, oracle policy, bootstrap limits,
source spans, artifact reproducibility.

**RISKS:** migration expands into a hidden full compiler rewrite and hides
semantic drift behind golden files.

**ESTIMATED_COMPLEXITY=VERY_HIGH**

**UNLOCKS:** evidence-based post-1.50 choices for parser, generics, debugging,
and additional native backends.

## Dependency graph

```text
1.39 -> 1.40 -> 1.41 -> 1.42 -> 1.43 -> 1.44 -> 1.45 -> 1.46
                         |                  |        |
                         +-----> 1.47 -----+--------+
                                      |
                         1.43/1.44 -> 1.48 -> 1.49 -> 1.50
                         1.45/1.46 ------------^       ^
                         1.39-1.49 -------------------+
```

All milestones remain independently gated. 1.48 may be parallelized with late
1.47 implementation only after the shared resource/error contract is closed;
otherwise the default sequence is linear to prevent semantic stacking.
