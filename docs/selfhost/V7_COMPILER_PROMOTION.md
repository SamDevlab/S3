# S3 V7 Compiler Promotion

Campaign state: `PARTIAL_CLOSED` on `feat/s3-v7-compiler-promotion-bootstrap-independence`.

## Definitive closeout — 2026-10-17

**Result: `PARTIAL_CLOSED`; technical promotion is not complete.** This is an
administrative closeout of the current V7 qualification attempt, not a claim
that S3C-NG is production-ready or at feature parity.

- PR [#331](https://github.com/SamDevlab/S3/pull/331) remains OPEN and Draft.
  No Ready transition, merge, tag, release, or default change is authorized.
- Exact tested source HEAD: `ac6b0f0d1b55d23279f42cbc4e6482b36fdffd99`.
  The final documentation commit may advance the PR head without changing this
  tested source. No executable/compiler/test logic changes are included in
  this closeout.
- Natural Tests workflow run `39040792079` targets that exact source HEAD.
  At closeout it had 11 successful jobs, 0 failed jobs, and 4 unit/renderer
  shards still in progress. This is `CI_PENDING`, not an all-green full-suite
  result. The native x86-64, S3C-NG promotion, exact-head seed, clean-checkout
  B-to-C fixed-point, and performance-characterization jobs had succeeded.
- All 18 currently listed feature families remain `PARTIAL`. Focused native
  execution and the B-to-C fixed point do not establish whole-language parity.
  Full negative-program, diagnostic/source-span, CLI, and ProjectTooling parity
  also remain unqualified.
- The exact-head Linux x86-64 bootstrap candidate was built and installed in a
  clean CI checkout from the immutable artifact in run `39040792079`. Its
  executable SHA-256 is
  `390f4c04f056396ec70352919b2e71d9be50fc6d9ba2f891eddfb8f4a6e216f8`; its
  source-graph SHA-256 is
  `07143ec7fe5a5f7cb7a1d97efe4eadefdc97b25db81e2cd548be867d041d3278`.
  The seed still derives from `python-reference-stage0`; the CI artifact is
  ephemeral, not a durable release. The release lock remains `UNPUBLISHED`.
- Performance characterization is not a promotion pass. On all five measured
  cases S3C-NG was slower than Python: small `20.235x`, multimodule
  ordering/search `2.311x`, real Pebble `1.523x`, self-source `2.369x`, and
  fresh CLI startup `1.078x`. The run recorded 341,980 KiB process peak RSS and
  4,144,716 KiB maximum observed child peak RSS across the measurement; these
  figures are not attributed to an individual provider. This is a material
  performance and memory risk, not evidence of speedup.
- Python remains the reference and default compiler on all platforms. S3C-NG
  remains opt-in and qualified only as a candidate on Linux x86-64. Windows
  compatibility remains on Python. No global support claim is made.
- V8 remains blocked pending a future explicit V7 technical-completion gate.
  This closeout does not start V8.

The remaining work is substantive: complete differential feature-family and
invalid-program/diagnostic coverage, broader user-command and ProjectTooling
qualification, resolve the observed performance/memory risk, and obtain
explicit owner approval before publishing or pinning a durable Linux seed.
Because those gates are not satisfied, the campaign closes as partial rather
than extending into another open-ended qualification cycle.

## V6 starting evidence

V6 is the merged baseline at `2eab8a43f07b7fc842c4036ea0fb0203a9d41d6c`.
Its native self-host and strict canonical, Assembly, object, and ELF fixed-point
claims are inherited evidence, not newly re-proven by this campaign.

At V7 start, `DEFAULT_COMPILER=PYTHON`,
`REFERENCE_COMPILER=PYTHON`, `DEFAULT_NATIVE_BACKEND=S3_X86_64`, and QBE is not
the default. Promotion remains opt-in until all V7 gates pass.

## Compiler boundary inventory

| Boundary | Current implementation |
| --- | --- |
| User CLI | `bootstrap.s3.cli:main`, installed as `s3` |
| Current source compile path | Python mode calls `compile_source` for one file and `compile_sources` for a source directory; S3C-NG mode sends a deterministic source set through the native provider |
| Python reference API | `compile_source` / `compile_sources` in `bootstrap/s3/pipeline.py` |
| S3C-NG source entrypoint | exported `ng_emit_source_set` in `selfhost/compiler_ng/modules.s3` |
| S3C-NG input | `S3NGIN01`: entry-module UTF-8 name and bounded source-unit path/content records; at most 4096 units and 64 MiB per unit |
| S3C-NG executable boundary | Linux x86-64 ELF plus `tools/native_selfhost_driver.c`; the driver transports bytes and invokes the exported entrypoint |
| S3C-NG output | `S3NGOUT1`: signed i64 status, source-byte length, event count, source bytes, then i64 events |
| Canonical IR boundary | NG IR event stream V24, width 8, decoded by `decode_ng_ir_events` into the shared `IRModule` |
| Shared validation/backend | Python `verify_ir`, optimizer, `generate_assembly`, and the existing backend registry |

The native S3C-NG frontend owns source-set parsing, type/semantic analysis,
lowering, and event emission. Python event decoding, canonical IR verification,
optimization, Assembly/backend generation, process orchestration, packaging,
and CLI presentation are separate host/toolchain responsibilities. S3C-NG CLI
mode must never call the Python source compiler as a fallback.

## Command boundary at campaign start

`USES_COMPILER_SEMANTICS` describes the command's result, not an implementation
accident in the current CLI (which presently invokes `compile_source` even for
some front-end inspection commands).

| Command | Uses semantic compilation | S3C-NG required for promotion | Current note |
| --- | --- | --- | --- |
| `doctor`, `targets` | NO | NO | Host diagnostic and target metadata; no source compilation |
| `tokens` | NO | NO | Python lexer/tooling output |
| `ast` | NO | NO | Python parser/tooling output |
| `check` | YES | YES | Must validate through the selected frontend and shared verifier |
| `ir` | YES | YES | Canonical IR view |
| `ir-json` | YES | YES | Versioned canonical serialization |
| `inspect` | YES | YES | Summary/IR/Assembly projections of a compiled program |
| `asm` | YES | YES | Shared Assembly backend |
| `run` | YES | YES | Shared hosted execution path |
| `native-asm` | YES | YES | Shared native x86-64 backend |
| `build` | YES | YES | Shared native toolchain |
| `run-native` | YES | YES | Shared native backend/toolchain |
| `ffi-build` | YES | YES | Selected provider emits IR/Assembly; FFI builder consumes that shared Assembly |
| `verify-ir` | NO | NO | Consumes existing serialized IR and invokes verifier |
| `format`, `docs` | NO | NO | Source tooling/documentation |
| `test` | YES | YES | `--compiler` and candidate path are forwarded to the shared provider; report schema v2 records the selected compiler; parity remains unqualified |
| `container inspect` | NO | NO | Project metadata and source inventory only |
| `container plan` | NO (describes runtime) | YES | Plan carries the selected compiler for its `s3 run` command |
| `container build` | NO (configures runtime) | YES | Embeds the selected compiler in the image's `s3 run` entrypoint; image build itself does not compile S3 source |
| `container run` | INDIRECT | YES | Docker invokes `s3 run`; compiler and optional candidate path are forwarded into the container |

`s3 doctor` reports the selected default and reference provider, candidate
availability, target, artifact SHA-256, source commit, trusted-release pin
state, and native toolchain availability. The release pin is reported
separately from candidate availability so a local development ELF is not
misrepresented as a trusted distributed seed.

## Qualification rule

The machine-readable command matrix and parity inventory are in
`V7_COMPILER_PARITY.json` (schema 2). The matrix is an inventory, not a passing
qualification claim. States must be backed by existing tests/spec/workloads
and may only be promoted from `UNTESTED` when the same source cases have run
through both compiler providers at the relevant comparison level. Scoped
evidence does not qualify an entire family; hosted IR execution does not stand
in for native S3C-NG execution or full feature parity. `PARTIAL` means one or
more focused differential tests pass while the complete repository-derived
family corpus or its required comparison levels remain unqualified; it is not
a promotion pass. The Python reference remains available explicitly
throughout V7.

The maintained `s3c-ng-promotion` Linux x86-64 job owns the native provider and
strict fixed-point tests once per CI candidate. The three Python-version unit
groups exclude only this marked native promotion group, avoiding repeated
multi-generation native bootstrap work while keeping it fail-closed on its
supported CI host.

## V7 provider implementation checkpoint

The existing CLI now accepts `--compiler python|s3c-ng` on semantic compile
commands. Python remains the default. Explicit S3C-NG selection fails closed
when the host/artifact/manifest is unavailable, the syntax mode is unsupported,
the native status is nonzero, or the emitted event stream is invalid. No
semantic Python fallback is attempted.

Both providers meet at `IRModule`; verifier, optimizer, Assembly generation,
hosted execution, x86-64 generation, native build/run, and FFI Assembly
generation remain shared. S3C-NG provider mode does not create a Python
`SemanticModel` or AST. The native source-set boundary now has an additive
`S3NGOUT2` response with bounded, separate diagnostic records while retaining
the `S3NGOUT1` legacy entrypoint and decoder. The focused implementation covers
missing modules, direct self-cycles, unknown imported symbols, and private
imported symbols; all other nonzero native statuses still fail closed as
transport errors. This is not full negative-program or diagnostic parity.
S3C-NG currently accepts source syntax 0.6 only and requires a Linux x86-64 ELF
candidate. The `s3c_ng_supported_now` command-matrix entries apply only to that
target; they do not claim support on Windows or other targets. No global
promotion has occurred, and Windows continues to use the Python reference path.

The local V24 increment adds borrowed immutable-slice type descriptors,
explicit hidden length parameters, and indexed slice-load lowering. The hosted
regression compares canonical IR with the Python reference, verifies the
result, and executes the slice-taking function with the same bounded slice
value. This is focused hosted evidence. Exact-head Linux CI run `38683054022`
also built and invoked immutable `&[i64]` exports through the pointer-plus-length
ABI, including forwarding both cells through a second S3 function. Mutable slice
stores and the broader slice corpus remain unqualified.

The native candidate rejection matrix checks ten invalid source-set cases
against the Python reference, covering module/import graphs, call arity and
types, aggregate fields, bytes builtins, and resource builtins. That matrix
proves rejection and guards native status values, not full diagnostic parity.
The new `S3NGOUT2` slice separately transports stable category, phase, code,
source-unit index, UTF-8 byte span, and message identifier for four import
failure codes. The host validates the bounded envelope and source span, maps a
single recognized record to the public semantic diagnostic, and does not
recompile through Python. The focused Linux test compares category, phase,
code, and source-location policy with the Python reference; exact displayed
message parity remains unqualified. A direct-cycle record uses an explicit
no-location sentinel because Python reports that cycle without a location.
Multi-record formatting and statuses without a record fail closed.
`S3NGOUT1` remains available through the legacy exported entrypoint. Focused
provider tests pass locally; the real native regression is Linux x86-64-only
and requires the exact-candidate CI gate. The broader negative corpus,
parser/type diagnostics, and full diagnostic parity remain open.

Compiler selection is offered on semantic compile commands, the test-manifest
runner, and project-test discovery API. `doctor`, `targets`, `tokens`, `ast`, `format`, and `docs`
remain explicit Python tooling paths; they do not accept a compiler override.
Test reports identify the selected compiler in `s3.test-report.v2`; aggregate
project-test reports use schema 2 and preserve the selected compiler identity.
ProjectTooling's host-side build/run API also accepts a compiler and
executable. The `container` subcommands retain Docker as the execution/image
backend. `inspect` reads project metadata; `plan`, `build`, and `run` accept
compiler selection for the runtime `s3 run` invocation. The optional
`--s3c-ng-executable` path is interpreted inside the image; choosing S3C-NG does
not package or silently fall back to a missing candidate. A source directory
is interpreted as a sorted set of `.s3` modules, with
`--entry-module` defaulting to `main`. A single S3C-NG source file is
transported as `main.s3`; an explicitly declared module other than `main`
requires a matching `--entry-module`.

`tools/build_s3c_ng_candidate.py` can make a local Linux candidate and a
deterministic schema-2 manifest. This development candidate is seeded from
Python reference-produced canonical IR (`python-reference-stage0`); it is not
the pinned trusted S3C-NG bootstrap artifact required for promotion. Candidate
ELF files remain local build outputs and are not committed or released.

The maintained workflow creates a per-exact-HEAD immutable GitHub Actions
artifact containing the candidate and schema-2 manifest, then consumes it from
a separate clean Linux checkout. The artifact name binds the source SHA within
the workflow run; GitHub verifies the uploaded artifact digest on download.
The clean-checkout gate additionally checks the executable SHA, source commit,
source-graph SHA, canonical compiler IR, Assembly, object, and ELF against the
manifest. The consumed seed records `python-reference-stage0` as its parent.
This is an ephemeral, same-workflow trust path used for CI qualification. It is
not itself a release asset; stable distribution is handled separately below.

The exact-head gate passed on `bf9a947412ff3f408cb030f89a6d2315049bfacd` in
Tests workflow run `38594968631` on 2026-10-14. The dedicated clean-checkout
job passed after downloading that run's candidate, and the S3C-NG promotion
job passed its maintained native fixed-point checks. This qualifies the
maintained CI path on that head; it does not establish durable bootstrap
distribution or complete compiler-promotion readiness.

## Performance characterization

The clean-bootstrap Linux x86-64 job runs
`tools/characterize_s3c_ng_provider.py` against its verified candidate. It
compares Python and S3C-NG on a small program, a real multimodule
ordering/search workload, a generated Pebble compiler workload, and the full
S3C-NG source set, then measures a fresh-process `check` command. Each provider
gets one warmup and three alternating O0 samples. IR and Assembly hashes must
match before timing data is accepted. The report is retained as a separate CI
evidence artifact; it is not a bootstrap seed. There is no fixed speedup
threshold. Promotion review considers pathological slowdown and startup
behavior, and records process plus maximum child peak RSS for the combined
measurement (not attributed per provider). Exact source HEAD
`ac6b0f0d1b55d23279f42cbc4e6482b36fdffd99` was characterized in run
`39040792079` on Linux x86-64. Ratios (S3C-NG/Python) were 20.235x small,
2.311x multimodule ordering/search, 1.523x real Pebble, 2.369x self-source,
and 1.078x fresh CLI startup. Process peak RSS was 341,980 KiB and maximum
observed child peak RSS was 4,144,716 KiB across the measurement; neither is
provider-attributed. Classification remains `CHARACTERIZATION_ONLY`; this is
not a speedup claim. Four unit/renderer shards were still pending at closeout.

## Stable bootstrap distribution preparation

The preferred durable carrier is a versioned GitHub Release asset named
`s3c-ng-bootstrap-linux-x86_64.tar.gz`. The deterministic packager is
`tools/package_s3c_ng_bootstrap.py`; the archive contains only the candidate
ELF and its schema-2 provenance manifest. The packaged lock records the release
tag, archive and executable SHA-256 values, source commit, source-graph digest,
Linux x86-64 target, and exact compiler/assembler/linker identities.
Before producing the archive, the packager now requires the manifest's source
commit to equal the checkout `HEAD`, requires compiler inputs to be clean, and
recomputes the checked-in compiler source-graph digest. It also fails closed if
the manifest omits compiler, assembler, or linker identity/version fields.

Acquisition is an explicit one-time command, `s3 bootstrap install s3c-ng`.
Normal compilation never downloads an artifact. Once a release pin is
published, installation verifies the archive digest before parsing it, checks
the manifest against the lock, validates the ELF and provenance, then installs
atomically under the S3 bootstrap cache. Missing, incompatible, modified, or
unpublished artifacts fail closed. On platforms other than Linux x86-64 the
Python reference remains available and S3C-NG is not promoted by this path.

This PR contains the installer and deterministic packager, but its lock remains
`UNPUBLISHED`: no durable release/tag has been published. The exact-head
candidate and provenance were produced and consumed successfully by the
ephemeral CI clean-checkout gate in run `39040792079`; this does not make that
artifact a stable carrier. Publication still requires the campaign owner's
explicit confirmation. `DEFAULT_COMPILER` remains Python.

The current PR candidate adds a native CLI regression using the `answer(42)`
source through `check`, IR projections, `inspect`, Assembly, hosted/native
execution, and build commands. It also routes relational-match and multi-module
workloads through `ir-json`, `run`, `build`, and `run-native`; `ffi-build` and
`test` are covered by the neighboring native CLI regression. It compares
reference artifacts/results and makes explicit S3C-NG fail if the CLI calls
its Python single-source compiler path. These remain narrow samples, not
qualification of every command against the supported-language corpus. The
native CLI, real-workload, immutable-slice FFI, and B/C/D fixed-point samples
passed the exact-head Linux promotion job in run `38683054022` for
`20af4034a4bcc5b2b842740624de614a98bfca60`; full Python test groups were still
running when recorded.

A Linux-only regression exercises one host-side `ProjectTooling` project
through Python and explicit S3C-NG providers, comparing canonical IR and
execution results. The same native test discovers two project test manifests
created in reverse order, compares deterministic ordering and name filtering,
and checks per-test hosted outcomes. These focused samples passed exact-head
Linux promotion run `38721603135` on `042af57f81ba94f9bc8e4aff360acf5935bc5748`.
The full ProjectTooling API and broad project/test-discovery corpus remain
unqualified.

The current worktree's focused hosted test passes using the repository's
sorting/search, hex-encoding, and CSV-parser workload sources and builders. It
compares canonical IR and execution with the Python reference. A separate Linux
x86-64 native candidate gate additionally compares source locations, verifies
the emitted IR, and executes each program through the native backend. That
native gate passed in exact-head run `38683054022` for
`20af4034a4bcc5b2b842740624de614a98bfca60`. This is a focused real-workload
corpus, not complete language-matrix qualification.

The current focused numeric regression closes contextual result typing for
constant integer expressions in `i64` and `tryte`, including grouped and
negated `tryte` boundaries, while keeping parameter-driven `tryte` arithmetic
dynamic. Constant `trit`/`tryte` overflow and underflow are rejected to match
the Python semantic reference. The hosted canonical-IR tests and adjacent NG
semantic boundary tests pass locally; the full numeric feature family remains
`UNTESTED`, and broader exact-head differential qualification is still required.

At exact HEAD `ed394e26b2aa8f4caa1a579daa8a77462910d6f5`, the Linux native
workload test adds focused `checked-i64-arithmetic` and generic
`vector<i64>` push/set/get/pop cases alongside ordering/search, hex encoding,
and CSV parsing. Native CI run `38769827678` passed the `native-x86-64` job
with 176 tests; the three Python unit shards each reported 4,625 passed and
180 skipped. The exact-head `Tests` workflow and the `S3 1.0 candidate gates`
and `M1.38 Docker capability closure` workflows all passed. This evidence is
limited to these workloads; the full feature families, diagnostic parity,
and remaining V7 promotion gates are still open.

## Current limitations

- Linux CI has qualified the actual S3C-NG ELF for explicit provider use,
  representative ordinary and multi-module programs, the maintained B/C/D
  compiler fixed-point path, focused ProjectTooling/discovery samples, and
  five focused native workloads. Exact-head run `38769827678` passed at
  `ed394e26b2aa8f4caa1a579daa8a77462910d6f5`: each Python unit shard reported
  4,625 passed and 180 skipped, and `native-x86-64` reported 176 passed.
  Parity across every semantic CLI command and the full supported-language
  matrix is still unqualified.
- `test` and ProjectTooling host-side build/run accept compiler selection.
  Focused native ProjectTooling build/run and sorted discovery/filter parity
  pass at the exact head above; broad project build/run and test-discovery
  parity remain unqualified. The `container` CLI remains a Docker
  interoperability workflow rather than a host compiler-selection path.
- The exact-head clean-checkout artifact path and maintained V7 native
  fixed-point gates passed on `bf9a947412ff3f408cb030f89a6d2315049bfacd`.
  The artifact is ephemeral and same-workflow. A deterministic, hash-pinned
  GitHub Release distribution path is now implemented, but the lock is still
  unpublished pending the final candidate and owner confirmation. The seed's
  Python Stage0 trust root remains explicit.
- The existing V6 fixed-point evidence remains historical; the V7 maintained
  promotion and clean-checkout gates are separate, newly passing evidence.
- The V24 event decoder is shared, but the full supported-language, invalid
  program, structured diagnostic, workload, and execution parity matrices are
  not yet qualified.
- FFI-relevant compilation has a Linux x86-64 promotion test that invokes
  `ffi-build` with the explicit S3C-NG candidate, loads the resulting shared
  library, and compares exported i64/f64 calls against a library built from
  Python reference IR. Exact-head Linux CI also qualified immutable-slice
  pointer-plus-length entry and forwarding through `relay`. Mutable-slice
  stores and broad slice parity remain unqualified; this does not qualify
  default promotion.
- A Linux promotion run on an earlier PR head exposed a fixed-point mismatch
  in static-string IDs for multi-module input. The decoder now assigns IDs in
  canonical function order, then source order within each function. The
  strengthened per-module static-string workload and native promotion gate
  passed in run `38594968631` on the exact head above.
- No compiler default has been changed; no release artifact is authorized.

## R2 implementation checkpoint — 2026-10-17

This checkpoint records implementation and focused evidence on PR #331; it
does not supersede the promotion gates above. The branch remains Draft and the
work is not a release qualification.

- Source branch/HEAD at test time: `feat/s3-v7-compiler-promotion-bootstrap-independence`
  / `864a5f48c1274572c70f352d28a39d0feddeedb9`. The focused changes were
  uncommitted at checkpoint time. The Linux x86-64 development candidate was
  ephemeral at `/tmp/s3-v7-r2-current6/s3c-ng`, SHA-256
  `e726901465c72b83cd5a5bd6c47fc098bd577e7cd90fbc9410df82c07801f5ce`,
  30,097,512 bytes, source-graph SHA-256
  `4b6dc2bf765e0e29b09d10bd729354c891e5eeab6691735f6ccbce7fdcd41b75`.
  It is not a durable or trusted bootstrap seed.
- A real candidate differential run selected 12 explicit cases across 12
  feature families. All 12 matched both canonical serialized IR and hosted
  execution, with zero failures. The report's scope is `CASE_SAMPLE_ONLY` and
  `parity_claim=NONE_CASE_SAMPLES_ONLY`; all 18 matrix families remain
  `PARTIAL`.
- Four native frontend diagnostic cases matched the reference code, category,
  phase, source unit, byte span, and host location: invalid byte, unsupported
  punctuation, unterminated string, and unexpected token. This is focused
  coverage, not broad invalid-program or diagnostic parity.
- Selected Linux x86-64 tests passed 53/53 in 36.53 seconds. Four additional
  focused native regression cases passed across the candidate-native runs.
  Windows focused tests passed 52 with 13 Linux-only skips; `compileall` and
  `git diff --check` passed. No full suite was run.
- Native artifact validation now reuses a successful executable SHA-256 only
  while executable and manifest file identities, manifest bytes, platform,
  architecture, and IR format remain identical; every inspection still
  validates the manifest and trusted pin. On the measured 30 MB candidate,
  cold inspection was 91.437 ms, warm inspection median 1.751 ms, and direct
  SHA-256 median 39.373 ms. This is a repeated-validation improvement, not a
  compilation-speedup claim.
- A lexer fast path classifies supported single-byte symbols once in the
  bounded character table and avoids repeating symbol recognition at each
  occurrence. Correctness-focused lexer and native tests passed. Same-host
  exploratory compiler timing did not establish a reliable causal improvement:
  the current candidate's Pebble median was 96,316.260 ms (164.982x Python),
  versus 94,216.738 ms (160.575x) for the older artifact; the small-program
  ratios were 8.811x and 9.406x respectively. These artifacts are different
  source snapshots, so the comparison does not attribute changes to the lexer
  or cache. The bounded full characterization timed out at 120 seconds during
  self-source; memory attribution and phase-level profiling remain open.
- CLI workflows and ProjectTooling have new focused provider-parity tests,
  including explicit failure when the selected native candidate is unavailable.
  The clean-bootstrap CI job now runs these tests against its exact-head
  artifact. CI for the resulting pushed HEAD must pass naturally before any
  promotion discussion. Python remains the reference/default; the release lock
  remains `UNPUBLISHED`; no PR merge, tag, release, or global promotion is
  authorized.

## UTF-8 diagnostic-span follow-up — 2026-10-17

- A multibyte invalid symbol exposed that the native diagnostic span could end
  inside a UTF-8 code point. The cause was width selection tied to the quote
  discriminator and to treating relation predicates as three-way comparisons.
  The corrected helper uses the language's boolean-trit contract (`-1` true,
  `0` false) and sequential UTF-8 lead-byte thresholds.
- The final local Linux x86-64 candidate was ephemeral at
  `/tmp/s3-v7-r2-utf8-final/s3c-ng`, SHA-256
  `52409e44e0115da051180d15725ed686a526c4f985563f571c1c66d9c4fa70c7`,
  30,068,920 bytes, source commit `77970b24237b5f9858daef4f08b479c6d8bf2330`,
  source-graph SHA-256
  `586f3b938e9cf31f2f24464d80d835f034c97192c4b91b6b70df8348d0af0689`.
- Seven native frontend diagnostic cases matched the reference through the
  provider boundary, including invalid spans of 1, 2, 3, and 4 UTF-8 bytes.
  Linux focused tests passed 8/8 in 49.34 seconds; Windows hosted diagnostic
  tests passed 7/7. `compileall` and `git diff --check` passed.
- The final candidate passed all 11 selected non-Pebble differential samples
  across 11 families at canonical-IR and hosted-execution levels. They remain
  `CASE_SAMPLE_ONLY`; no feature family is promoted. The earlier 12/12 result
  belongs to candidate `e7269014...`, before the UTF-8 source change.
- A near-final candidate `d870e767...` failed the full 12-case bounded corpus
  only on `maturity-pebble-compiler`. A separate single-case diagnosis confirmed
  the native compiler process timed out at 120 seconds; this was not a
  diagnostic mismatch. Pebble was not rerun on the final candidate. The timeout
  remains an unresolved performance/host observation, not a pass or a proven
  regression from the UTF-8 fix. No full suite or full characterization was
  run again.

Next engineering work remains performance/memory root-cause attribution and
expansion of repository-derived positive and negative differential coverage.
No family is promoted by this checkpoint.
