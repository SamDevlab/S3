# S3 V7 Compiler Promotion

Campaign state: qualification in progress on `feat/s3-v7-compiler-promotion-bootstrap-independence`.

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

## Qualification rule

The machine-readable command matrix and parity inventory are in
`V7_COMPILER_PARITY.json` (schema 2). The matrix is an inventory, not a passing
qualification claim. States must be backed by existing tests/spec/workloads
and may only be promoted from `UNTESTED` when the same source cases have run
through both compiler providers at the relevant comparison level. Scoped
evidence does not qualify an entire family; hosted IR execution does not stand
in for native S3C-NG execution or full feature parity. The Python reference
remains available explicitly throughout V7.

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
`SemanticModel` or AST. The native output status currently carries no structured
diagnostic payload, so negative-program and diagnostic parity remain
unqualified. S3C-NG currently accepts source syntax 0.6 only and requires a
Linux x86-64 ELF candidate.

The local V24 increment adds borrowed immutable-slice type descriptors,
explicit hidden length parameters, and indexed slice-load lowering. The hosted
regression compares canonical IR with the Python reference, verifies the
result, and executes the slice-taking function with the same bounded slice
value. This is focused hosted evidence. Exact-head Linux CI run `38683054022`
also built and invoked immutable `&[i64]` exports through the pointer-plus-length
ABI, including forwarding both cells through a second S3 function. Mutable slice
stores and the broader slice corpus remain unqualified.

The native candidate rejection matrix now checks ten invalid source-set cases
against the Python reference, covering module/import graphs, call arity and
types, aggregate fields, bytes builtins, and resource builtins. This proves
rejection and guards each current native status value; it does not qualify
stable diagnostic categories, codes, messages, or source spans. `S3NGOUT1`
currently returns only status, source bytes, and IR events; S3C-NG rejections
are surfaced as generic toolchain errors. Structured diagnostic transport and
parity remain an open promotion gate.

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
This is an ephemeral, same-workflow trust path, not a release asset or a
durable external distribution mechanism.

The exact-head gate passed on `bf9a947412ff3f408cb030f89a6d2315049bfacd` in
Tests workflow run `38594968631` on 2026-10-14. The dedicated clean-checkout
job passed after downloading that run's candidate, and the S3C-NG promotion
job passed its maintained native fixed-point checks. This qualifies the
maintained CI path on that head; it does not establish durable bootstrap
distribution or complete compiler-promotion readiness.

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
  The artifact is ephemeral and same-workflow; durable external bootstrap
  distribution remains undecided. The seed's Python Stage0 trust root remains
  explicit.
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
