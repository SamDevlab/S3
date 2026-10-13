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
| Canonical IR boundary | NG IR event stream V22, width 8, decoded by `decode_ng_ir_events` into the shared `IRModule` |
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
qualification claim. States must be backed by existing
tests/spec/workloads and may only be promoted from `UNTESTED` when the same
source cases have run through both compiler providers at the relevant comparison
level. The Python reference remains available explicitly throughout V7.
`PARTIAL` feature evidence names the tests and execution scope; hosted IR
execution does not stand in for native S3C-NG execution or full feature parity.

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

## Current limitations

- CLI selection is implemented, but core command parity has not yet been
  qualified using an actual S3C-NG ELF on Linux.
- `test` and ProjectTooling host-side build/run now accept compiler selection,
  but their S3C-NG parity is unqualified. The `container` CLI remains a Docker
  interoperability workflow rather than a host compiler-selection path.
- Bootstrap artifact distribution/trust and a clean-checkout maintained
  bootstrap gate are not yet established; V6 fixed-point evidence remains
  inherited, not a V7 rerun.
- The V22 event decoder is shared, but the full supported-language, invalid
  program, structured diagnostic, workload, and execution parity matrices are
  not yet qualified.
- A Linux promotion run on the initial PR head exposed a fixed-point mismatch in
  static-string IDs for multi-module input. The local decoder now assigns IDs
  in canonical function order, then source order within each function; focused
  hosted regressions pass, but this correction is not natively qualified until
  a new exact-head Linux promotion run completes.
- No compiler default has been changed; no release artifact is authorized.
