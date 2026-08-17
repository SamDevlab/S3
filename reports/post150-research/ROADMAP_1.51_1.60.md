# Recommended S3 Roadmap: M1.51 to M1.60

This is a research recommendation only. Official roadmap/spec files are not
changed. The sequence is dependency-first: ownership, constrained generics,
packages/build identity, then human tooling and bounded self-hosting.

## M1.51 — Composite Owned Values

- WHY_NOW: Dynamic bytes/text/collections cannot be fields of records, arrays, or enums; this is the largest application-model gap.
- DEPENDENCIES: M1.39-M1.50; fixed-value layout; dynamic buffer contracts.
- PUBLIC_SURFACE: bounded owned bytes, text, vectors, maps, and sets as explicitly declared aggregate fields.
- INTERNAL_ARCHITECTURE: ownership-aware aggregate layout, field paths, allocation identity, and deterministic destruction metadata.
- OUT_OF_SCOPE: general generics, GC, raw pointers, implicit growth, concurrency.
- LANGUAGE_SEMANTICS: explicit move/borrow/clone/drop; no owner use after move; no move while borrowed.
- IR_IMPACT: aggregate value descriptors and explicit ownership operations; no hidden aggregate return.
- LOWERING_IMPACT: deterministic field projection, construction, destruction, and failure paths.
- NATIVE_BACKEND_IMPACT: descriptor/aggregate ABI contract required before native promotion.
- EMULATOR_IMPACT: hosted ownership and allocation failure oracle.
- FFI_IMPACT: no new foreign ownership transfer.
- BUILD_TOOLING_IMPACT: none beyond capability/test manifest updates.
- DETERMINISM_CONTRACT: stable field order, layout identity, drop order, and allocation diagnostics.
- RESOURCE_LIMITS: existing 64 MiB default and logical maxima remain unchanged.
- ERROR_MODEL: deterministic allocation, borrow, bounds, and moved-value diagnostics/traps.
- TEST_TIER_REQUIRED: T0 + T1 ownership + T2 M1.51; T3 at closure.
- FOCUSED_GATES: nested owners, records/enums/arrays, branch joins, early returns, loop backedges, O0/O1 hosted.
- FINAL_CERTIFICATION_GATE: T3 cross-backend differential and required T4 merge candidate.
- ENVIRONMENT_DEPENDENCIES: Linux native for native descriptor evidence.
- RISKS: ABI ambiguity, destructor paths, partial construction, layout compatibility.
- EXIT_CRITERIA: normative aggregate ownership contract and hosted/reference gates pass; no generic syntax added.

## M1.52 — Aggregate Move, Borrow, and Drop Flow

- WHY_NOW: M1.51 layout is insufficient without control-flow-complete ownership transfer.
- DEPENDENCIES: M1.51.
- PUBLIC_SURFACE: no new broad syntax beyond aggregate-safe existing operations.
- INTERNAL_ARCHITECTURE: path-sensitive ownership state at joins, returns, loops, and exceptional traps.
- OUT_OF_SCOPE: exceptions, async, shared ownership, GC.
- LANGUAGE_SEMANTICS: lexical borrows, exact drop-once behavior, explicit clone.
- IR_IMPACT: ownership state and drop markers verified across CFG.
- LOWERING_IMPACT: edge cleanup and merge normalization.
- NATIVE_BACKEND_IMPACT: deterministic cleanup ABI and no double-drop.
- EMULATOR_IMPACT: reference lifetime oracle and negative diagnostics.
- FFI_IMPACT: preserve closed buffer ABI.
- BUILD_TOOLING_IMPACT: add T2 ownership profile.
- DETERMINISM_CONTRACT: identical CFG produces identical cleanup ordering.
- RESOURCE_LIMITS: bounded ownership bookkeeping and allocation limits.
- ERROR_MODEL: compile-time ownership diagnostics; deterministic runtime resource errors.
- TEST_TIER_REQUIRED: T0 + T1/T2 M1.52; T3 closure.
- FOCUSED_GATES: joins, early returns, backedges, nested borrows, clone/drop, failure cleanup.
- FINAL_CERTIFICATION_GATE: hosted/native differential and merge-candidate T4.
- ENVIRONMENT_DEPENDENCIES: Linux native optional until ABI gate is available.
- RISKS: path explosion and hidden cleanup effects.
- EXIT_CRITERIA: verifier rejects invalid ownership paths and all valid paths drop exactly once.

## M1.53 — Constrained Generic Functions V1

- WHY_NOW: Repeated specialized functions become costly after ownership is stable.
- DEPENDENCIES: M1.51-M1.52.
- PUBLIC_SURFACE: closed generic functions with explicit type parameters and a finite scalar/owned constraint set.
- INTERNAL_ARCHITECTURE: deterministic monomorphization and specialization identity.
- OUT_OF_SCOPE: traits, typeclasses, higher-kinded types, reflection, dynamic dispatch, generic fields.
- LANGUAGE_SEMANTICS: compile-time substitution only; no runtime type identity.
- IR_IMPACT: specialized concrete IR only; generic templates do not reach Assembly.
- LOWERING_IMPACT: stable specialization order and code-size accounting.
- NATIVE_BACKEND_IMPACT: each specialization uses existing concrete ABI.
- EMULATOR_IMPACT: execute specializations through the existing reference path.
- FFI_IMPACT: generic functions cannot cross FFI until concretely specialized.
- BUILD_TOOLING_IMPACT: specialization identity becomes a lock/build input.
- DETERMINISM_CONTRACT: canonical type-argument ordering and no environment-dependent names.
- RESOURCE_LIMITS: bounded instantiation count and code-size budget.
- ERROR_MODEL: deterministic constraint and specialization diagnostics.
- TEST_TIER_REQUIRED: T0 + T1 generic semantics + T2 generic subsystem; T3 closure.
- FOCUSED_GATES: valid/invalid constraints, recursive calls, deterministic identity, code-size limits.
- FINAL_CERTIFICATION_GATE: O0/O1 and hosted/native differential; T4 for global IR changes.
- ENVIRONMENT_DEPENDENCIES: native only for concrete specializations.
- RISKS: accidental trait system, code explosion, ambiguous inference.
- EXIT_CRITERIA: constrained functions work without traits or runtime dispatch.

## M1.54 — Parametric Records and Enums

- WHY_NOW: Generic functions alone cannot model reusable domain aggregates.
- DEPENDENCIES: M1.51-M1.53.
- PUBLIC_SURFACE: closed parametric records/enums with explicit type arguments.
- INTERNAL_ARCHITECTURE: nominal identity includes canonical arguments; acyclic layout remains mandatory.
- OUT_OF_SCOPE: open extension, reflection, higher-kinded types, generic recursion without bounds.
- LANGUAGE_SEMANTICS: concrete monomorphized layouts only.
- IR_IMPACT: concrete fixed layouts after specialization.
- LOWERING_IMPACT: field/payload projections use specialized layouts.
- NATIVE_BACKEND_IMPACT: concrete scalar/aggregate ABI only.
- EMULATOR_IMPACT: structural equality and ownership oracle over concrete values.
- FFI_IMPACT: only concrete exported layouts.
- BUILD_TOOLING_IMPACT: type-argument identities enter artifact inputs.
- DETERMINISM_CONTRACT: nominal identity and layout independent of source path.
- RESOURCE_LIMITS: bounded type depth and specialization count.
- ERROR_MODEL: deterministic arity, cycle, and layout conflict diagnostics.
- TEST_TIER_REQUIRED: T0 + T1 type identity + T2 aggregate subsystem; T3 closure.
- FOCUSED_GATES: nested parametric values, enum payloads, imports, cycles, ABI stability.
- FINAL_CERTIFICATION_GATE: differential and merge-candidate T4.
- ENVIRONMENT_DEPENDENCIES: Linux native for aggregate ABI evidence.
- RISKS: layout identity drift and specialization multiplication.
- EXIT_CRITERIA: concrete parametric records/enums are compatible with M1.51 ownership.

## M1.55 — Generic Ordered Vector V1

- WHY_NOW: vectors are the first high-value collection migration target.
- DEPENDENCIES: M1.51-M1.54.
- PUBLIC_SURFACE: generic ordered vector with explicit element constraints and capacity policy.
- INTERNAL_ARCHITECTURE: replace specialized duplication through a compatibility-preserving specialization layer.
- OUT_OF_SCOPE: generic maps/sets, iterators with hidden allocation, implicit growth, concurrency.
- LANGUAGE_SEMANTICS: explicit ownership and bounds; specialized ternary/native domains remain supported.
- IR_IMPACT: typed vector identity or verified parameterized descriptor, never an untyped collapse.
- LOWERING_IMPACT: element-size and clone/drop operations are specialization inputs.
- NATIVE_BACKEND_IMPACT: concrete element ABI and capacity checks.
- EMULATOR_IMPACT: reference vector semantics and deterministic order.
- FFI_IMPACT: no generic foreign ABI.
- BUILD_TOOLING_IMPACT: vector specialization identity is content-addressed.
- DETERMINISM_CONTRACT: stable iteration, insertion, clone, and specialization ordering.
- RESOURCE_LIMITS: explicit capacity and bounded allocation.
- ERROR_MODEL: deterministic bounds/capacity/ownership errors.
- TEST_TIER_REQUIRED: T0 + T1 vector + T2 collection; T3 closure.
- FOCUSED_GATES: tryte/i64/f64 compatibility, clone/drop, borrow, capacity, O0/O1.
- FINAL_CERTIFICATION_GATE: native differential and required T4 for IR/ABI changes.
- ENVIRONMENT_DEPENDENCIES: Linux native for concrete vector ABI.
- RISKS: breaking closed collection contracts or hiding representation staging.
- EXIT_CRITERIA: generic vector adds value without erasing existing specialized domains.

## M1.56 — Local Package Dependencies V1

- WHY_NOW: modules exist, but larger applications need reproducible dependency identity.
- DEPENDENCIES: M1.45 build graph/lockfile; M1.53-M1.55 specialization identity.
- PUBLIC_SURFACE: local path and pinned Git revision dependencies plus namespace identity.
- INTERNAL_ARCHITECTURE: locked dependency graph, cycle detection, offline resolution.
- OUT_OF_SCOPE: public registry, network package installation, implicit version ranges.
- LANGUAGE_SEMANTICS: imported nominal identity includes package identity.
- IR_IMPACT: artifact inputs record dependency identities.
- LOWERING_IMPACT: unchanged concrete lowering; foreign identity is locked.
- NATIVE_BACKEND_IMPACT: foreign library ABI records remain explicit.
- EMULATOR_IMPACT: deterministic local graph execution.
- FFI_IMPACT: package-local foreign ABI identity is locked.
- BUILD_TOOLING_IMPACT: lockfile v2 or compatible extension and offline diagnostics.
- DETERMINISM_CONTRACT: no timestamps, absolute paths, or mutable remote resolution.
- RESOURCE_LIMITS: bounded graph size and dependency depth.
- ERROR_MODEL: missing, cycle, revision, namespace, and ABI mismatch diagnostics.
- TEST_TIER_REQUIRED: T0 + T1 graph + T2 package subsystem; T3 closure.
- FOCUSED_GATES: path/Git dependencies, cycles, offline rebuild, namespace collisions.
- FINAL_CERTIFICATION_GATE: reproducible two-root build and merge-candidate T4.
- ENVIRONMENT_DEPENDENCIES: Git fixtures only; network not required for locked builds.
- RISKS: accidental package-manager scope and nondeterministic Git access.
- EXIT_CRITERIA: locked local dependencies build offline with identical identities.

## M1.57 — Content-Addressed Incremental Builds

- WHY_NOW: M1.45 has artifact identity but not dependency-aware reuse.
- DEPENDENCIES: M1.45 and M1.56 lock identities.
- PUBLIC_SURFACE: deterministic build plan and warm/cold diagnostics.
- INTERNAL_ARCHITECTURE: content-addressed artifact store keyed by canonical inputs.
- OUT_OF_SCOPE: timestamp caches, absolute path identity, remote cache service.
- LANGUAGE_SEMANTICS: no change.
- IR_IMPACT: artifact identity includes compiler/IR/target/profile inputs.
- LOWERING_IMPACT: no change; only reuse decisions.
- NATIVE_BACKEND_IMPACT: linker/toolchain identity is explicit input.
- EMULATOR_IMPACT: cached artifacts must preserve hosted results.
- FFI_IMPACT: foreign ABI records invalidate dependents.
- BUILD_TOOLING_IMPACT: cold/warm plan, invalidation, corruption detection.
- DETERMINISM_CONTRACT: identical content yields identical identity and plan.
- RESOURCE_LIMITS: bounded cache size and explicit eviction policy.
- ERROR_MODEL: stale/corrupt artifact is a miss or deterministic failure, never silent reuse.
- TEST_TIER_REQUIRED: T0 + T1 cache + T2 build + T3 multi-root.
- FOCUSED_GATES: source, lock, compiler, target, FFI, and dependency invalidation.
- FINAL_CERTIFICATION_GATE: reproducible cold/warm T4 at merge/release.
- ENVIRONMENT_DEPENDENCIES: toolchain identity probes; no Docker required.
- RISKS: incomplete invalidation and cache poisoning.
- EXIT_CRITERIA: warm builds reuse only exact compatible artifacts.

## M1.58 — Language Server Protocol V1

- WHY_NOW: stable package identity and diagnostics make bounded editor tooling useful.
- DEPENDENCIES: M1.56 package namespace; M1.57 incremental artifacts; diagnostics schema.
- PUBLIC_SURFACE: initialize, didOpen, didChange, diagnostics, hover, definition, symbols, deterministic completion.
- INTERNAL_ARCHITECTURE: request-scoped analysis over existing compiler APIs; no new semantic authority.
- OUT_OF_SCOPE: rename, references, code actions, refactors, build daemon, IDE platform.
- LANGUAGE_SEMANTICS: none.
- IR_IMPACT: read-only use of existing semantic/IR facts.
- LOWERING_IMPACT: none.
- NATIVE_BACKEND_IMPACT: none for V1.
- EMULATOR_IMPACT: none.
- FFI_IMPACT: none.
- BUILD_TOOLING_IMPACT: package-aware source identity and incremental invalidation.
- DETERMINISM_CONTRACT: stable diagnostics, symbols, ordering, and completion.
- RESOURCE_LIMITS: bounded request time, memory, and document size.
- ERROR_MODEL: protocol errors are distinct from compiler diagnostics.
- TEST_TIER_REQUIRED: T0 + T1 protocol + T2 LSP; T3 not normally required.
- FOCUSED_GATES: initialize, edits, diagnostics, hover, definition, symbols, completion.
- FINAL_CERTIFICATION_GATE: deterministic fixture matrix, not full compiler suite by default.
- ENVIRONMENT_DEPENDENCIES: no native runtime required.
- RISKS: accidentally creating a second compiler front end.
- EXIT_CRITERIA: editor facts are sourced from the authoritative compiler.

## M1.59 — Canonical Source and Developer Experience

- WHY_NOW: human usability remains the largest adoption gap after semantic foundation.
- DEPENDENCIES: M1.56-M1.58.
- PUBLIC_SURFACE: formatter, project init, build/test/run UX, error summaries, examples/templates, capability discovery.
- INTERNAL_ARCHITECTURE: thin deterministic CLI surfaces over existing contracts.
- OUT_OF_SCOPE: IDE-specific features, package registry, language redesign.
- LANGUAGE_SEMANTICS: none.
- IR_IMPACT: none.
- LOWERING_IMPACT: none.
- NATIVE_BACKEND_IMPACT: report native environment blocks clearly.
- EMULATOR_IMPACT: preserve hosted authority.
- FFI_IMPACT: surface ABI requirements without hiding them.
- BUILD_TOOLING_IMPACT: integrate locked graph and smart-test profiles.
- DETERMINISM_CONTRACT: formatter, diagnostics, and command output stable under canonical inputs.
- RESOURCE_LIMITS: bounded output and command timeouts.
- ERROR_MODEL: concise summaries retain machine-readable diagnostics.
- TEST_TIER_REQUIRED: T0 + T1 CLI/docs + T2 developer workflow.
- FOCUSED_GATES: formatting idempotence, init, check/build/test/run, error summary, capability metadata.
- FINAL_CERTIFICATION_GATE: deterministic project fixtures.
- ENVIRONMENT_DEPENDENCIES: native/WASI status remains explicit rather than hidden.
- RISKS: documentation drift and duplicated capability claims.
- EXIT_CRITERIA: a human can discover, build, test, and diagnose a small project predictably.

## M1.60 — Bounded Self-Hosted Manifest/Test Reader

- WHY_NOW: the project can validate a small self-hosted component without attempting a compiler rewrite.
- DEPENDENCIES: M1.56 lockfile, M1.57 artifact identity, M1.59 stable CLI/report contracts.
- PUBLIC_SURFACE: one manifest or test-report reader with a documented fallback.
- INTERNAL_ARCHITECTURE: bounded parser utility in S3 with Python oracle.
- OUT_OF_SCOPE: self-hosted compiler, package manager, JIT, runtime replacement.
- LANGUAGE_SEMANTICS: only the bounded parser subset required by the chosen artifact.
- IR_IMPACT: none or a tiny parser result contract.
- LOWERING_IMPACT: no compiler lowering replacement.
- NATIVE_BACKEND_IMPACT: optional candidate artifact only.
- EMULATOR_IMPACT: hosted S3 execution compared with Python oracle.
- FFI_IMPACT: none.
- BUILD_TOOLING_IMPACT: byte-identical or semantic-parity fixture integration.
- DETERMINISM_CONTRACT: exact bytes, bounded memory, stable errors, no timestamps/paths.
- RESOURCE_LIMITS: strict input-size, depth, and instruction limits.
- ERROR_MODEL: Python and S3 parsers classify identical malformed inputs.
- TEST_TIER_REQUIRED: T0 + T1 parser + T2 self-hosting component; T3/T4 only at promotion.
- FOCUSED_GATES: valid fixtures, malformed fixtures, limits, parity, fallback, determinism.
- FINAL_CERTIFICATION_GATE: two-oracle parity and promotion review.
- ENVIRONMENT_DEPENDENCIES: Python oracle remains authoritative; native certification optional.
- RISKS: scope creep into self-hosted compiler architecture.
- EXIT_CRITERIA: one bounded component is useful, proven, and safely fallback-capable.

