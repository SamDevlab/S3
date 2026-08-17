# Post-1.50 Deferred Candidates

These are deliberate deferrals, not forgotten work. Each item needs evidence
before it can displace the bounded roadmap.

## General generics and traits

`FEATURE=generic type parameters, traits, interfaces, and protocol dispatch`

`WHY_DEFERRED=`Current workloads are blocked by runtime data and resources;
M1.40 can use closed type-specific layouts. General polymorphism adds type
checking, inference, monomorphization, diagnostics, ABI, and determinism cost.`

`WHAT_MUST_EXIST_FIRST=`At least two maintained S3 libraries with measured
duplication that specialized APIs cannot reasonably address.`

`REVISIT_TRIGGER=`A self-hosted component or standard-library family becomes
dominated by semantic duplication rather than runtime capability.`

## Language-level concurrency, atomics, and async

`FEATURE=threads, atomics, channels, tasks, async/await, and structured
concurrency`

`WHY_DEFERRED=`No current memory-ordering, race, cancellation, scheduler, or
deterministic test contract exists. Network capability can start external-first.`

`WHAT_MUST_EXIST_FIRST=`Stable resource/error APIs, a measured parallel workload,
provider-level execution model, and a deterministic race/failure test strategy.`

`REVISIT_TRIGGER=`A real S3 workload is CPU or I/O blocked by provider-level
parallelism and cannot be served by external workers or processes.`

## Additional native backends

`FEATURE=Linux ARM64, Windows x86-64, and macOS ARM64 native backends`

`WHY_DEFERRED=`Each requires target ABI, layout, toolchain, runtime, CI, and
native regression ownership. Hosted execution already supports development on
multiple hosts, and WASI offers a cheaper portable execution contract.`

`WHAT_MUST_EXIST_FIRST=`A stable target abstraction, richer interop, reproducible
build graph, and sustained user demand for each target.`

`REVISIT_TRIGGER=`A target-specific deployment requirement is demonstrated by a
real application and an available CI/native environment.`

## Full parser and compiler self-hosting

`FEATURE=replace the Python parser/compiler/backend with an entirely self-hosted
S3 compiler`

`WHY_DEFERRED=`The current bounded Assembly candidate is useful differential
work, but a complete migration would combine parser, diagnostics, optimizer,
backend, file, build, and bootstrap risks in one campaign.`

`WHAT_MUST_EXIST_FIRST=`M1.50 component closure, stable source spans,
serialization, test runner, build lockfile, and measured migration scope.`

`REVISIT_TRIGGER=`A component-by-component plan can preserve Python oracle
equivalence with independent rollback and no semantic stacking.`

## Public registry and broad ecosystem package distribution

`FEATURE=remote package registry, Git dependency resolver, binary artifact
registry, and C++/Rust/Python object-level binding ecosystems`

`WHY_DEFERRED=`A public registry amplifies unresolved identity, security,
reproducibility, trust, and ABI policy. M1.45 only needs local path dependencies
and a content-hashed lockfile.`

`WHAT_MUST_EXIST_FIRST=`Stable package metadata, signed/reproducible artifacts,
version compatibility policy, and at least several independently maintained
packages.`

`REVISIT_TRIGGER=`Local graph use demonstrates a concrete distribution bottleneck
and the trust/reproducibility policy is approved.`

## Full Unicode, debugger, SIMD/GPU, and Docker closure

`FEATURE=grapheme-aware Unicode library, DWARF/GDB debugger, SIMD/GPU provider,
and real Docker certification`

`WHY_DEFERRED=`These are valuable but orthogonal to the first application chain;
they have high platform/toolchain cost or require evidence not present in this
research checkout. M1.38 Docker certification remains explicitly deferred.`

`WHAT_MUST_EXIST_FIRST=`A measured user workload, stable source spans and target
contracts, and an available controlled environment.`

`REVISIT_TRIGGER=`A post-1.50 workload or release requirement makes one of these
the dominant, reproducible blocker.`
