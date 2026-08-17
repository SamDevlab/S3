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
- PARSER_IMPACT: no new syntax required beyond existing aggregate declarations unless separately approved.
- SEMANTIC_IMPACT: ownership-aware aggregate legality, field paths, initialization, and moved-state diagnostics.
- IR_IMPACT: aggregate value descriptors and explicit ownership operations; no hidden aggregate return.
- SSA_IMPACT: aggregate owner state across projections, joins, and partial construction.
- LOWERING_IMPACT: deterministic field projection, construction, destruction, and failure paths.
- OPTIMIZER_IMPACT: preserve ownership operations and O0/O1 semantics; no ownership-eliding optimization by default.
- NATIVE_BACKEND_IMPACT: descriptor/aggregate ABI contract required before native promotion.
- EMULATOR_IMPACT: hosted ownership and allocation failure oracle.
- FFI_IMPACT: no new foreign ownership transfer.
- BUILD_TOOLING_IMPACT: none beyond capability/test manifest updates.
- DETERMINISM_CONTRACT: stable field order, layout identity, drop order, and allocation diagnostics.
- RESOURCE_LIMITS: existing 64 MiB default and logical maxima remain unchanged.
- ERROR_MODEL: deterministic allocation, borrow, bounds, and moved-value diagnostics/traps.
- T0_GATE: schema, parser smoke, and aggregate declaration diagnostics.
- T1_GATE: nested owners, records/enums/arrays, initialization and move/borrow diagnostics.
- T2_GATE: complete M1.51 aggregate ownership subsystem with O0/O1 hosted agreement.
- T3_GATE: cross-backend differential and native descriptor evidence at closure.
- T4_REQUIRED_AT_CLOSURE: required for a global/merge candidate contract change.
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
- PARSER_IMPACT: no new syntax beyond aggregate-safe existing operations.
- SEMANTIC_IMPACT: path-sensitive move, borrow, and destruction states at all CFG exits.
- IR_IMPACT: ownership state and drop markers verified across CFG.
- SSA_IMPACT: ownership transfer and drop markers remain valid at joins, returns, and backedges.
- LOWERING_IMPACT: edge cleanup and merge normalization.
- OPTIMIZER_IMPACT: preserve cleanup ordering and ownership liveness through O0/O1.
- NATIVE_BACKEND_IMPACT: deterministic cleanup ABI and no double-drop.
- EMULATOR_IMPACT: reference lifetime oracle and negative diagnostics.
- FFI_IMPACT: preserve closed buffer ABI.
- BUILD_TOOLING_IMPACT: add T2 ownership profile.
- DETERMINISM_CONTRACT: identical CFG produces identical cleanup ordering.
- RESOURCE_LIMITS: bounded ownership bookkeeping and allocation limits.
- ERROR_MODEL: compile-time ownership diagnostics; deterministic runtime resource errors.
- T0_GATE: CFG ownership schema and small valid/invalid flow smoke cases.
- T1_GATE: joins, early returns, backedges, nested borrows, clone/drop, and failure cleanup.
- T2_GATE: complete M1.52 ownership-flow subsystem with verifier evidence.
- T3_GATE: hosted/native differential and cross-subsystem cleanup evidence.
- T4_REQUIRED_AT_CLOSURE: required for a merge candidate with global ownership impact.
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
- PARSER_IMPACT: add only the closed generic-function syntax approved by the milestone contract.
- SEMANTIC_IMPACT: constraint checking, canonical type arguments, and specialization diagnostics.
- IR_IMPACT: specialized concrete IR only; generic templates do not reach Assembly.
- SSA_IMPACT: verify each concrete specialization independently; templates do not carry runtime ownership state.
- LOWERING_IMPACT: stable specialization order and code-size accounting.
- OPTIMIZER_IMPACT: optimize concrete specializations without changing monomorphization identity.
- NATIVE_BACKEND_IMPACT: each specialization uses existing concrete ABI.
- EMULATOR_IMPACT: execute specializations through the existing reference path.
- FFI_IMPACT: generic functions cannot cross FFI until concretely specialized.
- BUILD_TOOLING_IMPACT: specialization identity becomes a lock/build input.
- DETERMINISM_CONTRACT: canonical type-argument ordering and no environment-dependent names.
- RESOURCE_LIMITS: bounded instantiation count and code-size budget.
- ERROR_MODEL: deterministic constraint and specialization diagnostics.
- T0_GATE: generic syntax/schema smoke and specialization identity validation.
- T1_GATE: valid/invalid constraints, recursive calls, deterministic identity, and code-size limits.
- T2_GATE: complete constrained generic-function subsystem with concrete IR output.
- T3_GATE: O0/O1 and hosted/native differential for representative specializations.
- T4_REQUIRED_AT_CLOSURE: required when specialization changes have global IR impact.
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
- PARSER_IMPACT: add only closed parametric record/enum syntax approved by the contract.
- SEMANTIC_IMPACT: nominal type-argument identity, arity, cycles, and concrete layout legality.
- IR_IMPACT: concrete fixed layouts after specialization.
- SSA_IMPACT: field and payload ownership state uses the selected concrete layout.
- LOWERING_IMPACT: field/payload projections use specialized layouts.
- OPTIMIZER_IMPACT: optimize concrete layouts without collapsing nominal identity.
- NATIVE_BACKEND_IMPACT: concrete scalar/aggregate ABI only.
- EMULATOR_IMPACT: structural equality and ownership oracle over concrete values.
- FFI_IMPACT: only concrete exported layouts.
- BUILD_TOOLING_IMPACT: type-argument identities enter artifact inputs.
- DETERMINISM_CONTRACT: nominal identity and layout independent of source path.
- RESOURCE_LIMITS: bounded type depth and specialization count.
- ERROR_MODEL: deterministic arity, cycle, and layout conflict diagnostics.
- T0_GATE: type-argument schema, arity, cycle, and layout-conflict smoke tests.
- T1_GATE: nested parametric values, enum payloads, imports, cycles, and ABI identity.
- T2_GATE: complete parametric aggregate subsystem over concrete specialized layouts.
- T3_GATE: hosted/native differential and cross-module aggregate evidence.
- T4_REQUIRED_AT_CLOSURE: required for a merge candidate changing aggregate ABI or IR.
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
- PARSER_IMPACT: add only generic vector syntax and preserve existing specialized spellings.
- SEMANTIC_IMPACT: element constraints, capacity rules, ownership, and compatibility diagnostics.
- IR_IMPACT: typed vector identity or verified parameterized descriptor, never an untyped collapse.
- SSA_IMPACT: element move/borrow/clone/drop state follows the concrete vector specialization.
- LOWERING_IMPACT: element-size and clone/drop operations are specialization inputs.
- OPTIMIZER_IMPACT: preserve specialized ternary/native lowering while optimizing concrete vector operations.
- NATIVE_BACKEND_IMPACT: concrete element ABI and capacity checks.
- EMULATOR_IMPACT: reference vector semantics and deterministic order.
- FFI_IMPACT: no generic foreign ABI.
- BUILD_TOOLING_IMPACT: vector specialization identity is content-addressed.
- DETERMINISM_CONTRACT: stable iteration, insertion, clone, and specialization ordering.
- RESOURCE_LIMITS: explicit capacity and bounded allocation.
- ERROR_MODEL: deterministic bounds/capacity/ownership errors.
- T0_GATE: vector schema and compatibility smoke tests.
- T1_GATE: tryte/i64/f64 compatibility, clone/drop, borrow, capacity, and O0/O1 cases.
- T2_GATE: complete generic-vector collection subsystem with specialized-family compatibility.
- T3_GATE: native differential and cross-backend collection evidence.
- T4_REQUIRED_AT_CLOSURE: required for a merge candidate changing IR or ABI.
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
- PARSER_IMPACT: dependency manifest syntax and namespace fields only; no source-language redesign.
- SEMANTIC_IMPACT: package identity, import resolution, cycle, revision, and ABI consistency checks.
- IR_IMPACT: artifact inputs record dependency identities.
- SSA_IMPACT: none expected; compiled module ownership/SSA remains unchanged.
- LOWERING_IMPACT: unchanged concrete lowering; foreign identity is locked.
- OPTIMIZER_IMPACT: none expected beyond dependency identity in artifact inputs.
- NATIVE_BACKEND_IMPACT: foreign library ABI records remain explicit.
- EMULATOR_IMPACT: deterministic local graph execution.
- FFI_IMPACT: package-local foreign ABI identity is locked.
- BUILD_TOOLING_IMPACT: lockfile v2 or compatible extension and offline diagnostics.
- DETERMINISM_CONTRACT: no timestamps, absolute paths, or mutable remote resolution.
- RESOURCE_LIMITS: bounded graph size and dependency depth.
- ERROR_MODEL: missing, cycle, revision, namespace, and ABI mismatch diagnostics.
- T0_GATE: manifest schema, path/revision, and namespace smoke tests.
- T1_GATE: path/Git dependencies, cycles, offline rebuild, and namespace collisions.
- T2_GATE: complete package graph and lockfile subsystem.
- T3_GATE: reproducible two-root build and cross-package identity evidence.
- T4_REQUIRED_AT_CLOSURE: required for a merge candidate changing dependency/build identity.
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
- PARSER_IMPACT: no source-language syntax; only build-plan/cache metadata schemas.
- SEMANTIC_IMPACT: none to language semantics; validate cache input identity and invalidation.
- IR_IMPACT: artifact identity includes compiler/IR/target/profile inputs.
- SSA_IMPACT: none; cached SSA/IR artifacts are invalidated by exact input identity.
- LOWERING_IMPACT: no change; only reuse decisions.
- OPTIMIZER_IMPACT: optimizer/toolchain identity is an explicit cache input.
- NATIVE_BACKEND_IMPACT: linker/toolchain identity is explicit input.
- EMULATOR_IMPACT: cached artifacts must preserve hosted results.
- FFI_IMPACT: foreign ABI records invalidate dependents.
- BUILD_TOOLING_IMPACT: cold/warm plan, invalidation, corruption detection.
- DETERMINISM_CONTRACT: identical content yields identical identity and plan.
- RESOURCE_LIMITS: bounded cache size and explicit eviction policy.
- ERROR_MODEL: stale/corrupt artifact is a miss or deterministic failure, never silent reuse.
- T0_GATE: cache schema and fingerprint smoke tests.
- T1_GATE: source, lock, compiler, target, FFI, and dependency invalidation.
- T2_GATE: complete incremental-build subsystem with cold/warm plans.
- T3_GATE: reproducible multi-root build and corruption/invalidation evidence.
- T4_REQUIRED_AT_CLOSURE: required at merge/release for build-system promotion.
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
- PARSER_IMPACT: none; protocol documents source edits for the existing parser.
- SEMANTIC_IMPACT: expose existing diagnostics, symbols, hover, and definition facts through stable queries.
- IR_IMPACT: read-only use of existing semantic/IR facts.
- SSA_IMPACT: none; no new SSA authority is introduced.
- LOWERING_IMPACT: none.
- OPTIMIZER_IMPACT: none.
- NATIVE_BACKEND_IMPACT: none for V1.
- EMULATOR_IMPACT: none.
- FFI_IMPACT: none.
- BUILD_TOOLING_IMPACT: package-aware source identity and incremental invalidation.
- DETERMINISM_CONTRACT: stable diagnostics, symbols, ordering, and completion.
- RESOURCE_LIMITS: bounded request time, memory, and document size.
- ERROR_MODEL: protocol errors are distinct from compiler diagnostics.
- T0_GATE: protocol schema and initialize/shutdown smoke tests.
- T1_GATE: edits, diagnostics, hover, definition, symbols, and completion fixtures.
- T2_GATE: complete bounded LSP subsystem with authoritative compiler facts.
- T3_GATE: deterministic multi-document fixture matrix when package identity is affected.
- T4_REQUIRED_AT_CLOSURE: not normally required; only for global compiler/API impact or explicit promotion.
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
- PARSER_IMPACT: none; examples and CLI surfaces use existing syntax.
- SEMANTIC_IMPACT: none; expose existing diagnostics and capability metadata without a second authority.
- IR_IMPACT: none.
- SSA_IMPACT: none.
- LOWERING_IMPACT: none.
- OPTIMIZER_IMPACT: none.
- NATIVE_BACKEND_IMPACT: report native environment blocks clearly.
- EMULATOR_IMPACT: preserve hosted authority.
- FFI_IMPACT: surface ABI requirements without hiding them.
- BUILD_TOOLING_IMPACT: integrate locked graph and smart-test profiles.
- DETERMINISM_CONTRACT: formatter, diagnostics, and command output stable under canonical inputs.
- RESOURCE_LIMITS: bounded output and command timeouts.
- ERROR_MODEL: concise summaries retain machine-readable diagnostics.
- T0_GATE: CLI/schema and formatter idempotence smoke tests.
- T1_GATE: init, check/build/test/run, error summary, and capability metadata fixtures.
- T2_GATE: complete deterministic developer workflow over project fixtures.
- T3_GATE: not normally required; use only when build/package integration changes.
- T4_REQUIRED_AT_CLOSURE: not normally required; deterministic project fixtures are sufficient unless explicitly promoted.
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
- PARSER_IMPACT: implement one bounded manifest/test-report grammar subset in S3 with Python fallback.
- SEMANTIC_IMPACT: classify valid and malformed bounded inputs with parity to the Python oracle.
- IR_IMPACT: none or a tiny parser result contract.
- SSA_IMPACT: none; this is not a compiler ownership or control-flow change.
- LOWERING_IMPACT: no compiler lowering replacement.
- OPTIMIZER_IMPACT: none.
- NATIVE_BACKEND_IMPACT: optional candidate artifact only.
- EMULATOR_IMPACT: hosted S3 execution compared with Python oracle.
- FFI_IMPACT: none.
- BUILD_TOOLING_IMPACT: byte-identical or semantic-parity fixture integration.
- DETERMINISM_CONTRACT: exact bytes, bounded memory, stable errors, no timestamps/paths.
- RESOURCE_LIMITS: strict input-size, depth, and instruction limits.
- ERROR_MODEL: Python and S3 parsers classify identical malformed inputs.
- T0_GATE: bounded input schema, limits, and malformed-input smoke tests.
- T1_GATE: valid fixtures, malformed fixtures, limits, parity, fallback, and determinism.
- T2_GATE: complete bounded self-hosting component with Python oracle agreement.
- T3_GATE: two-oracle promotion matrix when the component crosses subsystem boundaries.
- T4_REQUIRED_AT_CLOSURE: only at explicit promotion; not required for initial bounded research implementation.
- ENVIRONMENT_DEPENDENCIES: Python oracle remains authoritative; native certification optional.
- RISKS: scope creep into self-hosted compiler architecture.
- EXIT_CRITERIA: one bounded component is useful, proven, and safely fallback-capable.
