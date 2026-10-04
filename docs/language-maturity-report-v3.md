# S3 Language Maturity Campaign V3

## Scope and Provenance

Campaign: `S3_LANGUAGE_MATURITY_V3_QBE_NATIVE_QUALIFICATION_AND_CROSS_PLATFORM_STABILITY_V1`.

This qualification extends the historical [V1 report](language-maturity-report-v1.md), [V1 matrix](language-maturity-matrix-v1.json), [V2 report](language-maturity-report-v2.md), and [V2 matrix](language-maturity-matrix-v2.json). It does not rewrite them. The V3 work qualifies the existing bounded QBE V1 scalar subset, makes the exact-byte public fixture independent of Windows line-ending conversion, and repairs a reproduced Windows descendant-process timeout race. It does not expand the language or QBE subset.

| Field | Evidence |
| --- | --- |
| Starting HEAD | `89d5d1de6e9a80e69c4d8d2e7514c1e29c58d945` |
| Implementation HEAD tested locally and by CI | `9eb943fcd070067c29a5a4d1215c8a75f3fe62c9` |
| Final documentation HEAD | The commit containing these V3 artifacts; its exact OID is recorded in PR #328 and the final campaign checkpoint (not embedded self-referentially) |
| Branch | `feat/s3-language-maturity-real-workloads-v1-20261004` |
| PR | [#328](https://github.com/SamDevlab/S3/pull/328), OPEN, DRAFT; do not merge |
| PR #327 | Unchanged at `55f73a31e8f049a1e6d805154355917921bbd53b`; open draft |
| QBE external revision | `c0818978acec60ebb6167fade60fb7012cbf20ca` |

The implementation head is the exact candidate used for the one Windows full-suite run. The QBE and other natural CI checks also identify that PR head. `FINAL_DOCUMENTATION_HEAD` and `FINAL_CI_HEAD` are intentionally separate from the implementation head; the latter is recorded only after the documentation commit's natural CI completes. No claim about CI on the documentation head is inferred from the implementation-head CI.

## Phase A: Existing QBE Subset on Real Linux QBE

`QBE_BACKEND_STATUS=EXPERIMENTAL_ORACLE`. `tools/qbe_oracle.py` translates normal verified S3 IR and does not enter the stable backend registry or normal CLI. The previously documented fail-closed scalar/control-flow subset is unchanged: i64/f64 scalar constants, moves, comparisons/relations, internal scalar calls, jumps, ternary `BRANCH3`, and scalar returns. Checked arithmetic remains rejected; no records, references, vectors, dynamic values, tryte mapping, or aggregate ABI were added.

The official QBE project identifies its source and release through [QBE's official source page](https://c9x.me/compile/code.html) and [release page](https://c9x.me/compile/releases.html). The qualified source was the upstream repository `git://c9x.me/qbe.git`, pinned to commit `c0818978acec60ebb6167fade60fb7012cbf20ca`. The upstream project is MIT-licensed. It was fetched and built ephemerally in the GitHub Actions runner's temporary directory, not vendored in S3. The build command was `make -C "$RUNNER_TEMP/qbe-source" -j2 CC=cc`; CI verified the fetched HEAD exactly matched the pin before building.

The successful `qbe-oracle-linux` job ran on GitHub Actions `ubuntu-24.04` (Ubuntu 24.04.5, Linux x86_64), with `cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0` and GNU Make 4.3. It built the pinned source, generated QBE assembly, assembled and linked native executables, and executed the native corpus. The test module completed `29 passed`: 19 structural/negative/determinism tests plus all 10 native cases (five existing scalar programs at O0 and O1). Those native cases compared `execute_ir`, Assembly emulator execution, S3 x86-64 native output, and QBE native exit status against the same observable scalar result. No performance claim is made.

Results:

- `QBE_SOURCE_PINNED=YES`; source fetch, exact revision check, and ephemeral build passed.
- `QBE_REAL_IL_ACCEPTANCE=PASS`; all existing generated corpus IL was accepted by the real QBE binary.
- `QBE_NATIVE_ASSEMBLY=PASS`, `QBE_NATIVE_LINK=PASS`, and `QBE_NATIVE_EXECUTION=PASS` for all 10 O0/O1 cases.
- `QBE_THREE_WAY_DIFFERENTIAL=PASS` for `execute_ir == S3 x86-64 == QBE native`; the additional Assembly emulator oracle agreed as well.
- `QBE_IL_DETERMINISTIC=PASS`; fail-closed negative cases passed.
- `QBE_FAILURE_CLASSIFICATION=NONE` for the qualified run.
- Windows has no QBE/native Linux toolchain in the local environment, so the local QBE module appropriately reported `19 passed, 10 skipped`; the required native evidence is from the pinned Linux CI job, not a Windows skip.

This is the first real native proof for the existing subset. QBE remains experimental: `DEFAULT_NATIVE_BACKEND=S3_X86_64`, no stable target or CLI target was added, and no QBE feature work is authorized by this report.

## Phase B: Exact-Byte Fixture Stability

The affected exact-byte fixture is `benchmarks/workloads/real_world/public-fixtures-v1/s3-1.6-public-compute-samples-v1.json`; its manifest is `benchmarks/workloads/real_world/public-fixtures-v1/public-datasets-v1.json`. Its canonical byte sequence is 7,483 bytes with SHA-256 `daf23bc747d7d483391efad709b47ead8854bf2f70405829b2833cd0fee2a924`. Before the fix, the Windows checkout with `core.autocrlf=true` produced SHA-256 `afb74dc054c8eabed4faaec1312aba07c3aea6cd2e2d6220173644a01363f54b` because the final LF was converted to CRLF. The Git blob and manifest already agreed; neither dataset content nor manifest was changed.

The narrowly scoped `.gitattributes` rule now marks only this exact immutable fixture `-text`, disabling checkout EOL conversion. `git check-attr` reports `text: unset` for the fixture. Fresh isolated checkouts with both `core.autocrlf=false` and `core.autocrlf=true` produced the same canonical worktree SHA and 7,483-byte length as the Git blob and manifest. The fixture blob and manifest are unchanged. Both checkout-mode focused checks passed; on Windows each reported `2 passed, 5 skipped` because the additional cases are platform-gated. The one Windows full suite then passed with no fixture hash failure.

## Phase C: Windows Process-Tree Timeout

The existing regression is `tests/test_reliability_runner_v2.py::test_r1_timeout_kills_descendant_process_tree`. A bounded pre-fix repeated run reproduced the failure in 12 of 20 runs (8 passed). The observed defect was not an increased-timeout need: the worker root could be reaped while its descendant survived and performed its delayed marker write. The initial classification was `RUNNER_IMPLEMENTATION_RACE`.

The repair assigns each Windows worker to a Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` immediately after process creation and before sending it work. Timeout terminates the job, and closing the job handle contains the entire worker process tree. The regression test now waits for a child readiness sentinel and records its PID/PPID before the timeout, then proves the child does not perform the delayed write. Timeout semantics were not relaxed, and no global timeout increase, retry, or xfail was introduced.

Post-fix bounded repetition passed 20/20 (minimum 5.104 s, median 5.198 s, maximum 5.841 s). The complete reliability-runner test module passed `14 passed` after the final test diagnostic enrichment. The process-tree semantic requirement remains intact.

## Maturity and Full-Suite Validation

The Phase A Assembly dynamic-runtime and Phase B Pebble/compiler-writing results remain the V2 evidence; no Assembly runtime or Pebble grammar/compiler implementation was changed in V3. The V2 inventory recorded 91 registered dynamic builtins and the existing parity workload families. Its bounded Pebble pipeline remains tokenizer → parser → indexed AST → semantic validation → tiny IR → independent verifier → bytecode emitter → existing VM, with `COMPILER_WRITING_CAPABILITY=PROVEN_BOUNDED`. The inherited normal-compiler scale evidence remains up to 53,319 source bytes, 100 functions, and 3 modules; it was not remeasured as a V3 scale experiment. The full V3 suite passed, so no Assembly/Pebble regression was observed.

Focused V3 validation before the full suite included the combined maturity/QBE-focused gate (`140 passed, 29 skipped`), QBE module on Windows (`19 passed, 10 skipped`), fixture checks under both autocrlf policies (`2 passed, 5 skipped` each), reliability module (`14 passed`), compileall, and `git diff --check`. Linux-native QBE was covered by CI, not by the Windows host.

Exactly one Windows full suite was run, on implementation HEAD `9eb943fcd070067c29a5a4d1215c8a75f3fe62c9`:

```text
Command: python -m pytest -o addopts= -q
Exit: 0
4347 passed, 369 skipped, 572 subtests passed
Elapsed: 4737.25 s (1:18:57)
Started: 2026-10-04T10:48:15.6888598-03:00
Ended: 2026-10-04T12:07:15.0612709-03:00
Transcript: %TEMP%\s3-language-maturity-v3-windows-full-20261004-104815.log
```

There were zero failures and zero timeouts. The full-suite transcript is external to the repository and was not committed.

## CI and Final Documentation Snapshot

The implementation-head natural pull-request run was `37206394370`, with `headSha=9eb943fcd070067c29a5a4d1215c8a75f3fe62c9`, completed successfully. All 14 checks passed, including `qbe-oracle-linux` (`29 passed`), the Python unit matrices, renderer, benchmark, native x86-64, Docker capability, differential, package, supply-chain, numeric-domain, and SSA gates. This result is attributed only to the implementation HEAD.

This report and `language-maturity-matrix-v3.json` are documentation-only additions. After their commit is pushed, that final documentation head must receive its own natural 14-check CI result before the campaign may be reported complete. `FINAL_DOCUMENTATION_HEAD` and `FINAL_CI_HEAD` refer to the same exact commit; their OID and CI result are recorded in PR #328 and the final campaign checkpoint. The containing commit cannot embed its own OID without making its content self-referential. Do not transfer the earlier implementation-head green status.

## Preserved Policy and Next Frontier

`DEFAULT_COMPILER=PYTHON`; `DEFAULT_NATIVE_BACKEND=S3_X86_64`; `QBE_BACKEND_STATUS=EXPERIMENTAL_ORACLE`. `SELFHOST_RESEARCH_STATUS=PAUSED`, `SELFHOST_REENTRY_AUTOMATIC=NO`, `STAGE1_V4_AUTHORIZED=NO`, and `SELFHOST_READY_FOR_REENTRY=NO`. PR #327 remains untouched. Keep PR #328 OPEN and DRAFT. No merge, Ready transition, tag, release, package publication, self-host restart, default backend promotion, or shutdown is authorized.

Recommend exactly one next bounded QBE frontier: **checked i64 arithmetic**, beginning with a narrowly specified checked add/subtract corpus and explicit overflow behavior. It is the closest fail-closed gap adjacent to the now-executed scalar/control-flow subset; it can be qualified without silently mapping checked S3 operations to wrapping QBE operations. This is a recommendation only; implement none of it in V3.

## Assessment

V3 closes the three targeted uncertainties: the existing QBE V1 subset has real pinned Linux native differential evidence; the exact-byte fixture is stable under both Windows `autocrlf` settings without changing fixture or manifest data; and a reproducible Windows process-tree race has a bounded general repair backed by 20/20 repetition and a green full suite. The campaign is complete only when the final documentation commit's exact-head natural CI is green and the PR remains Draft.
