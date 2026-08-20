# M1.91-M2.00 Milestone Contracts

Each milestone is one independently reviewed change set. A milestone must
have one branch and one pull request, and must be merged before the next
milestone is implemented. The limits and non-goals below are part of the
contract, not implementation instructions.

## M1.91 - Async control flow and select

- Goal: add explicit, deterministic control flow around resumable async work.
- User capability: await futures in bounded branches and select ready work.
- Architecture: async CFG/state-machine extension over M1.81-M1.83.
- Invariants: one poll owner, deterministic readiness order, no use-after-move.
- Limits: bounded select arity and suspension depth.
- Security: no unbounded polling or implicit detached task.
- Tests: parser, verifier, executable IR, emulator, differential behavior.
- Benchmark: correctness-first select/branch characterization only initially.
- Environment: Linux native evidence required; Windows may defer native parts.
- Non-goals: work stealing, cancellation policy redesign, network services.
- Exit: focused, cross-layer, full, native, and CI gates green.

## M1.92 - Synchronization primitives

- Goal: define bounded mutex, event, and coordination ownership.
- User capability: safely coordinate tasks without data races in the hosted model.
- Architecture: explicit ownership-aware async primitives and wake queues.
- Invariants: no double unlock, no lost wake, deterministic waiter order.
- Limits: bounded waiters, queue memory, and operation budgets.
- Security: fail closed on misuse and cancellation races.
- Tests: state-machine, contention, cancellation, and executor integration.
- Benchmark: bounded contention characterization after correctness.
- Environment: native Linux executor proof; platform deferments explicit.
- Non-goals: OS-wide shared-memory primitives or priority scheduling.
- Exit: M1.91 merged plus all synchronization gates green.

## M1.93 - Streaming HTTP and server boundaries

- Goal: extend bounded HTTP from client fixtures to streaming server paths.
- User capability: serve and consume bounded request/response streams.
- Architecture: framed streams over the M1.85 transport and async executor.
- Invariants: bounded headers/body, orderly close, no partial-frame confusion.
- Limits: connection, frame, queue, and timeout budgets.
- Security: request smuggling defenses and explicit origin policy.
- Tests: loopback framing, malformed inputs, backpressure, and shutdown.
- Benchmark: loopback throughput characterization; no public service dependency.
- Environment: Linux native socket evidence and Windows loopback evidence.
- Non-goals: HTTP/2, public deployment, or unbounded streaming.
- Exit: protocol, resource, differential, full, and CI gates green.

## M1.94 - TLS server and secure channels

- Goal: provide a verified server-side TLS boundary.
- User capability: host secure local services with configured certificates.
- Architecture: provider-backed TLS context with explicit certificate policy.
- Invariants: certificate and hostname policy cannot be disabled implicitly.
- Limits: handshake, certificate chain, record, and connection budgets.
- Security: fail closed on trust, hostname, protocol, and key errors.
- Tests: trusted, expired, wrong-host, untrusted, and shutdown fixtures.
- Benchmark: handshake characterization only after correctness certification.
- Environment: local certificate fixture plus Linux native validation.
- Non-goals: custom cryptography or public certificate automation.
- Exit: M1.93 merged, provider gate available, and all TLS gates green.

## M1.95 - Package resolution and registry v2

- Goal: resolve versioned packages through a bounded registry graph.
- User capability: deterministically select verified package versions.
- Architecture: read-only registry v2 layered on M1.86 content identity.
- Invariants: digest, origin, version, and dependency identity remain bound.
- Limits: graph depth, package count, response bytes, and cache size.
- Security: no dependency confusion or unverified cache exposure.
- Tests: lock resolution, conflicts, cycles, bad digest, and eviction.
- Benchmark: cold/warm resolution characterization with pinned fixtures.
- Environment: offline fixture registry; no public network dependency.
- Non-goals: package publishing or mutable remote indexes.
- Exit: deterministic resolver and cache gates green on the merged base.

## M1.96 - Signed indexes and trust policy

- Goal: authenticate registry indexes and explicit trust policy decisions.
- User capability: accept packages only from configured trusted publishers.
- Architecture: signed canonical index envelopes over M1.87 provider boundary.
- Invariants: key, publisher, origin, digest, and policy are auditable.
- Limits: index size, key count, signature size, and verification time.
- Security: rotation, revocation, unknown-key, and downgrade rejection.
- Tests: valid, tampered, rotated, revoked, and provider-unavailable cases.
- Benchmark: verification characterization only; no synthetic crypto timing.
- Environment: vetted provider required for PASS; otherwise DEFERRED.
- Non-goals: private-key storage or home-grown signature algorithms.
- Exit: trust policy proof and provider-aware CI gates green.

## M1.97 - AArch64 native object and link integration

- Goal: produce and validate complete AArch64 object/link artifacts.
- User capability: build runnable Linux AArch64 artifacts from full S3 programs.
- Architecture: extend M1.88 object, relocation, ABI, and toolchain boundaries.
- Invariants: target identity, ABI, relocations, symbols, and entry are exact.
- Limits: supported relocation set and bounded program size.
- Security: no host-target confusion or unchecked external linker invocation.
- Tests: ELF/object/link/relocation structural and native differential tests.
- Benchmark: native artifact characterization on a real AArch64 host only.
- Environment: Linux AArch64 toolchain or runner required for native PASS.
- Non-goals: macOS behavior or cross-target emulation claims.
- Exit: Linux native object and link certification is complete.

## M1.98 - Cross-platform backend parity

- Goal: align supported target contracts without weakening target identity.
- User capability: use equivalent source programs across registered backends.
- Architecture: shared contracts with target-specific lowering and validation.
- Invariants: semantics, ABI, diagnostics, and deterministic metadata agree.
- Limits: only registered targets and explicitly supported feature subsets.
- Security: no silent fallback to a different target or ABI.
- Tests: source differential matrix, object validation, and toolchain errors.
- Benchmark: cross-target characterization only with equivalent workloads.
- Environment: Linux x86-64, Linux AArch64, and macOS ARM64 evidence separated.
- Non-goals: adding unregistered targets or changing language semantics.
- Exit: parity matrix and native target gates are green.

## M1.99 - Runtime and codegen optimization

- Goal: optimize measured hot paths after capability correctness is stable.
- User capability: lower cost for verified workloads without semantic change.
- Architecture: one narrowly scoped optimization per reviewed campaign.
- Invariants: source, IR, emulator, native, and differential behavior preserved.
- Limits: pinned workload, reproducible counters, and rollback evidence.
- Security: no removal of safety checks or bounds without proof.
- Tests: focused regression, structural codegen, full suite, and native proof.
- Benchmark: pinned comparable protocol; characterization is not promotion.
- Environment: stable Linux native toolchain and independent reference required.
- Non-goals: speculative optimization or benchmark-specific special cases.
- Exit: measured improvement and no unresolved correctness or reproducibility gap.

## M2.00 - Release candidate and language stability gate

- Goal: certify a reproducible, documented language release candidate.
- User capability: consume a stable candidate with explicit compatibility scope.
- Architecture: deterministic bundle, license, manifest, target matrix, and policy.
- Invariants: source compatibility, reproducible bytes, and no hidden publication.
- Limits: declared feature set and supported target matrix only.
- Security: signed provenance, dependency policy, and release artifact checks.
- Tests: full suite, native matrix, package verification, and reproducibility.
- Benchmark: report only pinned comparable results; no fabricated claims.
- Environment: release CI and clean canonical main required.
- Non-goals: automatic public release or post-gate implementation.
- Exit: all prior milestones merged, release evidence complete, and review gate green.
