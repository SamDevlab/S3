# M1.81-M1.90 Publication Correction Report

```text
CORRECTION_CAMPAIGN=M181_M190_PUBLICATION_CORRECTION_20260819
ORIGINAL_PUBLICATION_REVIEW_HEAD=8ba7858c3b9a5ddb5de667479d185afe7f572ab1
CAMPAIGN_BASE_SHA=cd6804f72757d6936ca1ec6c20d5badf55d1aac4
CORRECTION_BRANCH=feature/m181-m190-autonomous-20260819
CORRECTION_HEAD=this documentation commit and its ancestors
CORRECTION_REMOTE_SOURCE_REVIEW=PASS_PENDING_LOCAL_EXECUTION
CORRECTION_LOCAL_TEST_STATUS=PENDING
READY_FOR_PR=NO_PENDING_LOCAL_FOCUSED_GATE
MERGE_EXECUTED=NO
TAG_CREATED=NO
RELEASE_CREATED=NO
M1_91_STARTED=NO
INSTRUCTION_LIMIT=100000
```

## Scope

The publication review of the original M1.81-M1.90 evidence head identified implementation gaps that were not justified by the original local T4. This correction line addresses those findings without rewriting the original T4 or presenting old test evidence as proof for new code.

## Corrective implementation

- **M1.81:** async execution is now compiler-owned executable async IR. `run_source()` routes async entries through resumable IR, and focused coverage checks PENDING/resume/READY value preservation rather than merely inspecting side metadata.
- **M1.82:** source `Future<T>` is recognized as a move-only ownership wrapper, can be created/moved/passed/awaited, imported async aliases retain module-qualified identities, and closed generic async calls materialize deterministic specialization-specific executable/frame identities.
- **M1.83:** task admission is one atomic reservation transaction; queued vs active poll ownership is explicit; wake-during-poll is deferred; cooperative cancellation is serialized after an active poll instead of racing it.
- **M1.84:** process stdout/stderr are streamed into a shared hard byte budget during execution. Overflow/timeout kills and reaps the child instead of first capturing unbounded output.
- **M1.85:** a real bounded TCP/HTTPS HTTP/1.1 transport exists. HTTPS uses certificate-required, hostname-checked TLS and request/header/body/timeout limits fail closed. Deterministic fixture and loopback tests remain local-only.
- **M1.86:** the registry now routes through the bounded HTTPS client, binds canonical registry origin into immutable object identity, independently verifies SHA-256 before cache insertion/exposure, and remains read-only.
- **M1.87:** the selected production signature path is Ed25519 through the optional vetted `cryptography` provider. Canonical payload binds key id and HTTPS source identity in addition to package identity, digest, publisher, and bounded provenance. No private-key persistence path is introduced.
- **M1.88/M1.89:** Linux/macOS ARM64 now accept complete compiler `AssemblyProgram` input through bounded AArch64 program lowering, explicit AAPCS64 ABI metadata, target selection, runtime symbol/relocation build plans, and a bounded platform-toolchain provider boundary. Native assemble/link/execution certification remains deferred on the Windows campaign host and is not inferred from structural lowering.
- **M1.90:** structural PASS requires target-specific validation rather than arbitrary bytes. Release candidates require Apache-2.0 license text, record Apache-2.0 metadata, verify the deterministic bundle, and still cannot publish.

## Publication-review findings closed in source

The correction branch was re-reviewed against the concrete publication blockers. The following source-level gates are now present:

- async `run_source()` dispatches an async entry to executable async IR instead of ignoring the async IR side channel;
- module compilation builds async module metadata and specialization identities before executable async IR lowering;
- task admission, active-poll ownership, deferred wake, and cancellation serialization share the executor synchronization root;
- process capture applies the byte budget while stdout/stderr are being drained and kills/reaps on overflow;
- HTTP has a real socket transport and secure default TLS context while deterministic fixture transport remains injectable;
- registry object fetching uses the bounded HTTP(S) client and verifies digest before cache insertion;
- production signature verification selects Ed25519 from `cryptography` with no custom crypto fallback;
- Linux/macOS ARM64 integration lowers full public S3 Assembly opcode input through direct operations or explicit runtime-helper ABI calls, with native execution kept as a separate certificate;
- release-candidate structural PASS is validator-backed and Apache-2.0 license text is mandatory.

This is a **source review only**. It does not convert the correction commits into tested evidence. Local execution remains mandatory before PR publication.

## Historical test truth

The original global T4 remains exactly the run captured before these publication corrections:

```text
ORIGINAL_T4_HEAD=8aca581571c59a1c7efbf3575b6c47420c9fd725
ORIGINAL_T4_SELECTED=359
ORIGINAL_T4_PASS=336
ORIGINAL_T4_FAIL=0
ORIGINAL_T4_TIMEOUT=23
ORIGINAL_T4_EXIT=1
ORIGINAL_T4_RESTARTED=NO
```

Four timeout nodes were independently observed passing after that run; the remaining timeout nodes were not converted to PASS. This historical T4 **does not certify the publication-correction commits**.

## Required publication gate

Before a PR may be created/merged for the corrected branch, execute on the exact final correction HEAD:

1. `python -m compileall bootstrap/s3`;
2. focused M1.71/PR182 and M1.81-M1.90 correction tests;
3. compiler/module/generic/backend-registry cross-layer tests;
4. `git diff --check` and clean source worktree;
5. real Ed25519 provider test when the optional `cryptography` dependency is available. If unavailable, record the provider execution certificate as deferred rather than silently converting the skipped test to PASS.

Do not restart the historical T4 merely to make old evidence green. Because this correction changes the normative compiler async path, decide whether a new broad smart test/T3 or publication T4 is warranted only after the focused gate is clean.
