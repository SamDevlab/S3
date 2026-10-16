# Capability matrix

Statuses describe this checkout at the pinned compiler revision, not future
V7 behavior. “Usable” means demonstrated in this worktree, with the scope
listed; it does not imply production suitability.

| Capability | Implemented | Tested | Practically usable | Requires integration | Missing | Blocked by compiler / environment |
|---|---|---|---|---|---|---|
| S3 diagnostics | Yes; existing compiler diagnostics are surfaced as JSON with source excerpt | Yes; good and bad source | Yes for one source file | IDE wiring is included in the VS Code adapter | Rich multi-file diagnostics UI | No compiler diagnostic changes made |
| LSP stdio | Existing server reused; adapter adds push diagnostics and conservative formatting | Yes; initialize/open/change/close/requests/shutdown/reconnect | Yes for supported VS Code actions | Local extension packaging/install is user initiated | Completion dispatch; safe global rename | Existing transport advertises completion but does not dispatch it |
| LSP navigation | Existing document symbols, hover, definition, references, workspace symbol requests | Yes; protocol integration and astral UTF-16 column conversion | Yes; workspace references/symbols are limited to open documents | Workspace-wide index | Workspace-wide rename and completion | Existing analysis/transport scope |
| Formatting | Existing conservative formatter reused | Yes; VS Code formatting request and formatter tests | Yes; normalizes line endings/trailing whitespace only | None for supported source | Opinionated style formatter | No compiler dependency |
| Project tooling | Existing manifest inspect/build/run reused by toolkit | Yes; temp project check/build/explicit hosted run | Yes for current hosted project model | Package injection into general `ProjectTooling` | Dependency-aware project build command | Native toolchain unavailable on this Windows host |
| Offline package reuse | Existing package manifests/lock resolver; lab assembles contained source sets | Yes; package lock/source hashes and cross-app imports | Yes in lab apps using repository-local sources | General project/package workflow ergonomics | Remote registry publishing/download | None for local examples |
| Application execution | Existing test runner and emulator | Yes; five applications, exact expected integer outputs | Yes in hosted mode | Linux native qualification | Native and FFI app fixtures | Linux x86_64 compiler/linker unavailable on this Windows host; no FFI fixture qualified |
| Balanced ternary utility | Experimental S3 module; does not change official `trit`/`tryte` | Yes; positive, negative, zero, boundary and out-of-range cases in app | Yes within documented 19-trit integer range | Broader formatting/tritwise API | Arbitrary precision and digit-wise operations | Bounded by implementation contract, not claimed as core language support |
| Local VS Code extension | Syntax grammar, local stdio client, VSIX packager | Yes; Node protocol tests and archive validation | Yes after manual local VSIX installation | User selects checkout/Python path | Marketplace publication, global auto-install | None for local packaging |
| Native / FFI | No qualified ecosystem fixtures yet | Unsupported paths tested to remain unsupported | No | Platform-specific CI/manual Linux host and ABI fixture | FFI samples and ABI matrix | Current host is Windows; campaign prohibits ABI/compiler changes |

The existing standard library and examples already cover common collections,
sorting/searching, text/CSV parsing, hex encoding, vector/science operations,
and compiler/VM demonstrations. The new libraries intentionally target gaps
that can be implemented with the pinned language: integer summaries,
bounded balanced ternary, and strict bounded key/value records.
