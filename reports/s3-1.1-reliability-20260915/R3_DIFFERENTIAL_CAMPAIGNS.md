# S3 1.1 R3 — Differential campaigns and replay

Date: 2026-09-15

## Scope

R3 adds deterministic differential orchestration on top of the merged R0/R1/R2 contracts. It does not change S3 source semantics, IR, optimizer behavior, hosted runtime behavior, native backend code, package metadata, or dependencies.

## Implemented

### Hosted differential

Every selected valid generated case is executed through the isolated R1 worker as:

```text
hosted O0
hosted O1
```

The worker hashes the canonical observable scalar result. Equal result hashes are PASS. A stable cross-path mismatch is classified `MISCOMPILE`.

### Bounded Linux x86-64 shard

A separate R3 worker module extends the already-frozen request/response protocol with the previously unavailable `RUN_NATIVE` implementation. It uses the existing certified Linux x86-64 backend/toolchain boundary and compares the exact `program returned: N\n` runtime result through the same canonical scalar hash used by hosted execution.

The native shard is bounded to at most 32 generated cases per campaign. Each selected native case compares:

```text
hosted O0
hosted O1
native O0
native O1
```

The R1 parent watchdog continues to own the hard outer timeout and process-tree kill boundary.

### Nondeterminism confirmation policy

A first disagreement is not immediately called a miscompile. The affected path(s) are re-executed twice with the exact same case bytes, compiler head, optimization and backend.

```text
same path changes across repetitions -> NONDETERMINISM
same paths stay stable but disagree with each other -> MISCOMPILE
```

Stable crashes, timeouts, resource-limit failures and unexpected rejections preserve their own outcome class rather than being relabeled as miscompiles.

### Replay bundle

Every non-PASS case can emit a bounded replay directory keyed by case ID:

```text
<input>/
  input.s3
  metadata.json
  result.json
  replay.json
```

The bundle stores exact source bytes and SHA-256, deterministic case metadata, observations, failure signature, compiler head and hashes of the replay metadata/result files. JSON is canonical and the frozen R0 replay-bundle size limit is enforced.

## Checked-in focused tests

`tests/test_reliability_differential_v2.py` covers:

- hosted O0/O1 PASS;
- stable hosted mismatch -> MISCOMPILE;
- changing repeated observation -> NONDETERMINISM;
- stable TIMEOUT preservation;
- valid case rejection -> UNEXPECTED_REJECTION;
- four-path native selection;
- stable native mismatch -> MISCOMPILE;
- bounded native-shard limit;
- deterministic first-N native selection;
- canonical replay bundle and content hashes.

`tests/test_reliability_worker_r3.py` covers:

- native observable hash compatibility with hosted scalar hashing;
- exact runtime output parsing;
- non-zero native runtime exit classification;
- fail-closed native environment unavailability;
- forwarding of frozen execution limits.

## Existing backend contract reused

R3 does not create a second native backend. It reuses `NativeToolchain.detect()`, `generate_native_assembly(...)`, build/run behavior, and the stable standalone runtime convention `program returned: N\n` already present in the 1.0 line.

## Evidence boundary

The current ChatGPT runtime does not have the private repository mounted as an executable checkout. GitHub Actions runner provisioning is also still tracked as unavailable under issue #284.

Therefore this report does **not** claim that the new repository tests or a real S3 differential campaign executed here.

In particular, the following release-quality evidence gates remain open until real execution:

```text
R3_HOSTED_O0_O1_DIFFERENTIAL=NOT_YET_EXECUTED
R3_LINUX_X86_64_BOUNDED_DIFFERENTIAL=NOT_YET_EXECUTED
```

The following implementation contracts are complete and reviewable independently of that environment debt:

```text
R3_DIFFERENTIAL_ORCHESTRATION=IMPLEMENTED
R3_NATIVE_WORKER=IMPLEMENTED
R3_NONDETERMINISM_CONFIRMATION_POLICY=IMPLEMENTED
R3_REPLAY_BUNDLE=IMPLEMENTED
R3_NATIVE_SHARD_BOUND=32
R3_PRODUCTION_COMPILER_DELTA=NONE
R3_DEPENDENCY_DELTA=NONE
```

## Promotion rule

R3 implementation may land without pretending the execution gates are green because it is additive reliability tooling and tests only. Issue #283 must keep hosted/native differential execution unchecked until actual repository-capable evidence is obtained.

R4 minimization may use the integrated failure-signature/replay structure, but release-quality maintenance closure at R5 still requires the missing real R3 campaign evidence.
