# Native and FFI qualification — PR #332

Evidence below was produced from a clean detached checkout of implementation
commit `eabe4f3311a40464d7d96791d6d70e7d7474480e`. The compiler identity stayed
fixed at `2eab8a43f07b7fc842c4036ea0fb0203a9d41d6c`.

## Execution environment

- Ubuntu 24.04.5 x86-64 userland under WSL1; reported kernel:
  `4.4.0-26100-Microsoft`.
- Python 3.12.3, GCC driver 13.3.0, GNU assembler 2.42, GNU linker 2.42,
  `readelf` and `nm` available.
- This is not WSL2 or a native Linux kernel. The five generated x86-64 ELF
  executables did run and return the expected results in this environment, but
  the strict native-Linux-host gate remains partial until the same evidence is
  reproduced on WSL2 or a Linux x86-64 host. No container daemon was available.

## Five application results

Hosted execution, compile-only, and native execution were run from the clean
checkout. Each native report includes the existing native test-runner result
and a separately built, `readelf`-verified ELF64 x86-64 executable that was run
twice under a 10-second timeout. Both runs returned the hosted result and exited
with status 0. Native artifacts were hashed and removed with their temporary
directories; hashes identify these outputs, not a cross-toolchain reproducible
binary guarantee.

| Application | Hosted / native result | Source SHA-256 | Fixture SHA-256 | ELF SHA-256 |
|---|---:|---|---|---|
| balanced-state-audit | 53007 / 53007 | `d19495c4900347645af89b1339b7faa06f02ab4d05c5cbcd69047273383124d5` | `2403bd260137b9fbc4c3537fbd31a2d7c012ba316f550a1a26de069305975f1a` | `fe2a4d0a97d3399c4c17c5cca0a18ebef970441b2c459cfe34e0e34c8e345bcb` |
| data-quality-report | 10701 / 10701 | `089fbead90023415d68c17591f4d6cfdaf401e7af23606fd455965efe478a413` | `f1a33bb84462cbd45144d8fed4d29b9b0bf83a2166f8106a7f69920f491fb596` | `44cc15f4b3ff6b8c0cabef719a4c7a342d90f1f1205ba4f5dffda704bd4053fc` |
| bounded-event-log | 30615 / 30615 | `1883207d2982c57e8bd6c1e41f4d97ef17868cde788081893d3f8dd81dc6a7c4` | `a20965b603d3209803e47308a5ad7408a58d1ce565204af0f41d6bec19468977` | `20559a9a6ee8eb04d4f3265ab6b3fb49714369cfe37a8ed2202067601242e4f1` |
| graph-path-report | 309 / 309 | `4e0375a52444c66e08a3b122e0d3346ff8bfb4602dad6b820205946678980cea` | `397fee372d3423615537464f71b5bfa55431e25d5177a6922a5d1d35a273a556` | `54073382e0b60782ff814c59134cb26fc7306308638feb5694384ce36f19efd7` |
| linear-regression-report | 210 / 210 | `68023001dc61e16b14ffecec7c2cc02f73e581d9f69449bb3d239fdceb4a40bc` | `35a3101cbcfb57a83be317ceb7f8e87ab30641b54e5e665ce43adedf06bac605` | `825c8a64fee04d1bee687da4df16e56768daeb2dcc1624d93e51111773c03ad1` |

All five package graphs resolved from repository-local sources without package
downloads. Package-lock SHA-256 values:

| Application | Package lock SHA-256 |
|---|---|
| balanced-state-audit | `945d09a88eb7aa05228c44d13a303aeaf8a6f93d1ebb00fe3d4da33ba3b83267` |
| data-quality-report | `a7d0c4cd39dde71ac1b871c8a1d767e0e1fba6955b7fb5a26156a02a6d997d35` |
| bounded-event-log | `8ce73c51ad6c92f47197661c9e4a207b417bbb0145df9dabbd018de234c09746` |
| graph-path-report | `9c46b71c3769cd46d5d93577ff887e2db0f65c721da67d4e5d80a86022e02eee` |
| linear-regression-report | `5926e95f5933d519f0288aca1a2a4b08fafc6a71e96df25abd7b945b733f68fa` |

Package-source SHA-256 values:

- `s3-balanced-ternary`: `9ca383735bc9688e2fcda7db11907f92113da4e87764b9359aacd38e9fb7b5a2`
- `s3-integer-summary`: `364a5eae921258e430bbbbd14cda39fd1169f9ad071ce95aca5533e16a8a7ee7`
- `s3-key-value-records`: `c8bf104704dd3ef00c84f7c84b921f158f03886262ec3272b4d877a7f4789fbf`

## Real FFI result

`ffi-native-library` exports `s3_add_i64(i64, i64) -> i64` using the declared
`sysv-amd64` contract. The source was compiled through the existing S3
`build_shared_library()` API to a temporary ELF64 `DYN` shared object. `nm -D`
confirmed the symbol; a separate Python `ctypes` subprocess declared both
arguments and the result as `c_int64`, loaded the `.so`, and made all five calls.
The source signature is compared against the compiler-produced IR before any
library load or native call.

- Source SHA-256: `6bdaa4f4cea6d4410a705ed76fc1a77d5d4ea55e5d5c8d83962476bcf4ff62f7`
- Package-lock SHA-256: `1e31a425f230f4f4bfc8f7a25db1c63c8eb6df17746d9afc6d956adbd0e8f99b`
- Produced library path: `/tmp/s3-ffi-qualification-5uzow832/libs3_ffi_reference.so`
  (ephemeral; removed after the run).
- Shared-library SHA-256: `082e29bc5ff1af7a81dc899a3face313b538a1799a04bfa3fc87a0ef35052a71`
- Positive cases: `(0,0)->0`, `(23,19)->42`, `(-10,3)->-7`,
  `(i64_min,0)->i64_min`, `(i64_max,0)->i64_max`; all passed, including repeated
  calls in one process.
- Safe negative cases passed: invalid signature description, missing symbol,
  nonexistent library path, unsupported ABI, and incompatible platform. No
  mismatched native call was attempted.
- The `.so` lived only in a temporary directory and was removed after hashing
  and verification.

## Clean checkout and editor

The clone was detached at the exact implementation commit above; the compiler
pin resolved to the required full SHA, and the checkout remained clean after
all runs (including the ignored VSIX output). In that clone: discovery passed;
hosted 5/5, compile-only 5/5, native execution 5/5, FFI build/load/call passed;
and the six learning-path tests passed.

The VSIX was rebuilt from this checkout (`s3-language` 0.1.0; main
`extension.js`; S3 language metadata, grammar, and client scripts present).
Archive SHA-256: `c3923a395a9e05be3f1336fc4d43c3fc169957219c0d1adbf340852ba7dd06d4`.
The smoke rebuild from the final report HEAD produced archive SHA-256
`3e8544c9e6ea46d28c22e40250052aeb819c3c3883139aea2dffbf3be4a0ddd5`; all nine
archive entries and their uncompressed bytes matched. The packager preserves
filesystem timestamps, so ZIP timestamps (and therefore the whole-archive
hash) vary between builds; byte-identical VSIX output is not claimed.
Its local installation was verified with VS Code 1.141.0 in a temporary,
isolated user-data and extensions directory; no Marketplace publication or
global extension installation was performed. The packaged extension resolves
the Python language-server entrypoint from the configured S3 checkout; that
server and the pinned LSP module were present. The extension's commands remain
explicit; opening a source file does not run an S3 program.

## Test notes and disposition

- Windows `tests/ecosystem`: 10 passed, 2 Linux-only tests skipped; VS Code
  client tests: 2 passed; learning path: 6 passed.
- Clean Linux-userland `tests/ecosystem/test_application_lab.py`: 10 passed.
- The full ecosystem test module was also attempted in WSL1. Its VS Code test
  could not spawn Node there: the supplied `/usr/local/bin/node` wrapper exposes
  the ELF loader as `process.execPath`, while `/usr/bin/node` returns
  `Exec format error` in this WSL1 environment. The same extension tests passed
  on Windows, and the clean-checkout VSIX build and isolated installation
  passed.
- The formal native-host gate remains **PARTIAL** pending WSL2 or native Linux
  x86-64 confirmation. No compiler, IR, backend, workflow, V7, production, or
  global machine configuration was changed.

## VirtualBox Linux x86-64 qualification — PR #332

This qualification supplements the WSL1 evidence above and supersedes its
partial native-host disposition for the Linux x86-64 scope tested here. The
earlier WSL1 evidence remains unchanged.

### VM and toolchain

- SSH target: configured alias `s3-vm` → `127.0.0.1:2222`, forwarded by
  VirtualBox to guest port 22. The pre-existing ED25519 host key in
  `known_hosts` had fingerprint
  `SHA256:Pjt/4EVV0X1kvK/x2laamfvdFaEndBZ1th+dMqvdTmo`; every SSH session used
  `StrictHostKeyChecking=yes`.
- VirtualBox VM: `Ubuntu server` (the separately registered `S3` VM was not
  started or changed). `VBoxManage` reported the SSH NAT forwarding rule;
  `systemd-detect-virt` identified the guest as `oracle`.
- Guest: Ubuntu 26.04 LTS, real Linux kernel `7.0.0-31-generic`, `x86_64`.
  `lscpu` reported 3 vCPUs and 8 GiB RAM. The guest root filesystem had no free
  blocks, so the exclusive workspaces, checkouts, venv, downloaded tooling,
  builds, and logs were kept under `/tmp` on its tmpfs (over 2 GiB available).
  No existing home-directory data was cleaned or overwritten.
- Python 3.14.4; GCC/`cc` 15.2.0; GNU `as`, `ld`, and `readelf` 2.46. Pytest
  9.1.1 was installed only in a temporary Python venv. Node was absent from the
  VM, so Node.js v24.22.0 LTS was downloaded from the
  [official Node.js distribution](https://nodejs.org/dist/v24.22.0/) into the
  temporary workspace and its archive was checked against the published
  `SHASUMS256.txt` (`cc2f601cee82d9a5a233302fe307abc600727035fd7d2c3a3571755989e95008`).
  Neither tool was installed globally.

### Repository and fixed compiler

- PR branch: `feat/s3-parallel-ecosystem-real-applications`.
- Tested implementation SHA: `e36c42f86d8d23cdfb64998dd563ed1c8601e02b`;
  PR branch head was verified at this SHA before both clones.
- Compiler baseline: `2eab8a43f07b7fc842c4036ea0fb0203a9d41d6c`. The baseline
  commit object was fetched into each isolated clone, and
  `git diff --quiet <baseline> HEAD -- bootstrap/s3` passed. Tests ran from
  detached HEAD; the clean reproduction clone was clean both before and after
  testing.

### Five application results

Compile-only, hosted, and native runs passed for all five applications. Every
native executable was verified by `readelf` as ELF64 x86-64, executed twice
under the lab timeout, returned the expected value on both runs, exited 0, and
produced no stderr. The package graphs resolved from repository-local sources.

| Application | Hosted / native result | Native ELF SHA-256 |
|---|---:|---|
| `balanced-state-audit` | 53007 / 53007 | `fe2a4d0a97d3399c4c17c5cca0a18ebef970441b2c459cfe34e0e34c8e345bcb` |
| `data-quality-report` | 10701 / 10701 | `44cc15f4b3ff6b8c0cabef719a4c7a342d90f1f1205ba4f5dffda704bd4053fc` |
| `bounded-event-log` | 30615 / 30615 | `20559a9a6ee8eb04d4f3265ab6b3fb49714369cfe37a8ed2202067601242e4f1` |
| `graph-path-report` | 309 / 309 | `54073382e0b60782ff814c59134cb26fc7306308638feb5694384ce36f19efd7` |
| `linear-regression-report` | 210 / 210 | `825c8a64fee04d1bee687da4df16e56768daeb2dcc1624d93e51111773c03ad1` |

Source, fixture, and package-lock digests observed on this SHA:

| Application | Source SHA-256 | Fixture SHA-256 | Package-lock SHA-256 |
|---|---|---|---|
| `balanced-state-audit` | `d19495c4900347645af89b1339b7faa06f02ab4d05c5cbcd69047273383124d5` | `2403bd260137b9fbc4c3537fbd31a2d7c012ba316f550a1a26de069305975f1a` | `945d09a88eb7aa05228c44d13a303aeaf8a6f93d1ebb00fe3d4da33ba3b83267` |
| `data-quality-report` | `089fbead90023415d68c17591f4d6cfdaf401e7af23606fd455965efe478a413` | `f1a33bb84462cbd45144d8fed4d29b9b0bf83a2166f8106a7f69920f491fb596` | `a7d0c4cd39dde71ac1b871c8a1d767e0e1fba6955b7fb5a26156a02a6d997d35` |
| `bounded-event-log` | `1883207d2982c57e8bd6c1e41f4d97ef17868cde788081893d3f8dd81dc6a7c4` | `a20965b603d3209803e47308a5ad7408a58d1ce565204af0f41d6bec19468977` | `8ce73c51ad6c92f47197661c9e4a207b417bbb0145df9dabbd018de234c09746` |
| `graph-path-report` | `4e0375a52444c66e08a3b122e0d3346ff8bfb4602dad6b820205946678980cea` | `397fee372d3423615537464f71b5bfa55431e25d5177a6922a5d1d35a273a556` | `9c46b71c3769cd46d5d93577ff887e2db0f65c721da67d4e5d80a86022e02eee` |
| `linear-regression-report` | `68023001dc61e16b14ffecec7c2cc02f73e581d9f69449bb3d239fdceb4a40bc` | `35a3101cbcfb57a83be317ceb7f8e87ab30641b54e5e665ce43adedf06bac605` | `5926e95f5933d519f0288aca1a2a4b08fafc6a71e96df25abd7b945b733f68fa` |

### Native FFI

The existing `ffi-native-library` fixture built an ELF64 `DYN` shared object;
`readelf` verified the artifact and the exported `s3_add_i64` symbol was found.
The declared ABI was `sysv-amd64 (i64, i64) -> i64`. A separate Python `ctypes`
process loaded the `.so`, made all five calls, and exited 0. Positive cases
`(0,0)`, `(23,19)`, `(-10,3)`, `(i64_min,0)`, and `(i64_max,0)` all passed;
the five safe negative cases (invalid signature, missing symbol, missing
library, unsupported ABI, incompatible platform) all rejected as expected. No
native call with an incorrect signature was attempted.

- Source SHA-256: `6bdaa4f4cea6d4410a705ed76fc1a77d5d4ea55e5d5c8d83962476bcf4ff62f7`
- Package-lock SHA-256: `1e31a425f230f4f4bfc8f7a25db1c63c8eb6df17746d9afc6d956adbd0e8f99b`
- Shared-library SHA-256: `082e29bc5ff1af7a81dc899a3face313b538a1799a04bfa3fc87a0ef35052a71`
- The `.so` was temporary and removed after hashing and verification.

### Clean reproduction and validation

A second clone was created at the same detached SHA with a clean initial
worktree. It independently repeated hosted and native execution, the FFI
build/load/calls, and the learning path. All functional results and all five
native ELF hashes matched the first clone; the FFI library hash also matched.
The learning path passed 6/6.

- `python -m pytest tests/ecosystem -q`: 14 passed.
- Focused LSP tests (`tests/test_m158_lsp.py` and
  `tests/test_m213_lsp_transport.py`): 9 passed.
- VS Code client/server Node tests: 2 passed; extension Python tests: 2 passed.
- VSIX rebuilt in the clean clone. All 9 archive entries were checked against
  their source bytes. This build's archive SHA-256 was
  `86c973728752d88f38c73a4ede3c969ccdec010b03033201672d35d370b0bb22`; as
  noted above, ZIP timestamps can make whole-archive hashes vary.
- No GitHub Actions were invoked. No compiler, backend, IR, ABI, V7, production,
  or global machine configuration was modified. No merge or release was made.

**Disposition:** native ecosystem and FFI qualification pass for the tested
VirtualBox Ubuntu Linux x86-64 environment and the pinned compiler baseline;
this evidence makes no claim about other kernels, architectures, or physical
hardware.
