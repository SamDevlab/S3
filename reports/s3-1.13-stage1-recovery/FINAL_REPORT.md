# S3 1.13 Stage1 Recovery and Reproducibility Report

## Result

`PARTIAL_SOURCE_RECOVERED_SEMANTICALLY_REPRODUCIBLE`

The original Stage1 source bytes and the four-file source set were recovered, preserved, and versioned. The Stage1 focused qualification and the seven recorded corpus outputs reproduce semantically, with the recorded Assembly output hashes matching. The campaign cannot claim bit-reproducibility of a separately built Stage1 artifact: the reported 139,740-byte artifact identity is the raw SHA-256 and size of the recovered `.s3` source itself, and no independent build command or separate binary was recovered. The Linux full suite also has one verifier correctness failure and one environment-capacity failure.

## Source Provenance

The expected path `selfhost/compiler/s3c_stage1.s3` was absent. The exact candidate was found at `selfhost/compiler/stage1_compiler_v1.s3` in the intended local campaign worktree, `C:/Users/samue/.codex/worktrees/s3-1-13-stage1-compiler/S3-language`. At discovery it was an untracked local source, not a source recovered from an earlier Git commit, stash, reflog, or unreachable Git object. Its raw SHA-256 and byte count match the historical candidate identity exactly. The source was preserved externally before qualification and is now versioned in this branch.

| Source file | Bytes | Raw SHA-256 | Final Git blob |
|---|---:|---|---|
| `selfhost/compiler/stage1_compiler_v1.s3` | 139740 | `894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c` | `75f9af5347c7d6c0b8b6f8a1808c82a69c84de65` |
| `selfhost/substrate/generic_lexer_state.s3` | 207645 | `298d8c459caf68a34e402a3439800a7905f93e364a30f6a089f9516cafd134d8` | `feee5b37143e1e303d966b54ed644bf776531d02` |
| `selfhost/substrate/output_sink.s3` | 5009 | `f2bd628b4da29ba73eb666911f6792f01edee6b6f7b8855209066f1c8468ad8d` | `add8eec817891c4dc9de133b0058f9aa76395187` |
| `selfhost/substrate/verifier_kernel.s3` | 94295 | `fd591e9d2a2234ebfe50e558859f8db627777d9d7440695fa337a89acce6107a` | `4a145429d5552ebc3b4a2aa05828e579127cdbca` |

Recovered source manifest SHA-256: `89820fc7d8db1f0db5608e6051902638b34d9fb1b5231ab192f418650b30fd09`. The original recorded source-tree fingerprint `4a5fc8f3ce57f66c35bc8610f3ec365e8390c5f16c0a5d08354e30fd50f93224` is retained as historical evidence; its generating algorithm was not independently reconstructed.

## Reproduction Evidence

The focused command `python -m pytest -q -rA tests/test_s3_1_13_stage1_compiler.py` passed: 19 passed, 0 failed. Its coverage includes host-fallback guards, accepted/rejected source cases, deterministic output, and parsing/execution of emitted S3 Assembly.

Seven original recorded cases were reproduced with the same input SHA-256 values and exactly matching S3 Assembly artifact SHA-256 values and byte counts: arithmetic-5, arithmetic-42, zero-argument-call, forward-function-call, typed-parameters, immutable-locals, and nested-calls-and-multiplication. The original recorded post-freeze unseen input (180 bytes, SHA-256 `2cf533562f25a4d15c8d5aa33c3ba283024c605f539c58f6f38f4c003b27960e`) was not recovered, so that exact case was not rerun. A separately created `RECOVERY_UNSEEN_SOURCE` after freezing the recovered manifest passed; the candidate result was 38, matching the Python reference, and the emitted artifact parsed and executed.

No recovered qualification path delegated Stage1 tokenization, parsing, semantic identity, IR construction, verification, or rendering to a Python fallback. Python remains the orchestrator/reference compiler; downstream Assembly parsing and execution are not Stage1 host fallbacks.

The historical artifact SHA-256 (`894a76a5...46a44c`) and size (139,740 bytes) equal the raw identity of `stage1_compiler_v1.s3`. No separate built artifact or authoritative build recipe was found. Therefore `rebuilt_artifact_sha256` is unavailable and `STAGE1_ARTIFACT_BIT_REPRODUCIBILITY=UNRESOLVED`, not PASS. The seven emitted Assembly artifacts are independently bit-identical to their recorded outputs; that is output reproducibility, not proof of rebuilding the Stage1 candidate artifact.

## Platform Gates

- Windows full suite: PASS, 4,284 passed, 349 skipped, 0 failed, exit 0. The tested recovered source raw SHA-256 was unchanged by the later Git EOL-preservation commit.
- Linux full suite: FAIL, 4,631 passed, 0 skipped, 2 failed, exit 1, on candidate HEAD `1487eb15f9ca151550861a4772f76509403e32f6`. Transcript: `C:/Users/samue/AppData/Local/Temp/s3-1.13-stage1-recovery-20260929-062653/linux-full-suite-git-1487eb15.txt`.
- `python -m compileall -q bootstrap/s3`: PASS.
- `git diff --check`: PASS.
- Established tracked high-signal secret scan: PASS.

The first Linux attempt used a source tar without `.git`; tests requiring `git show HEAD:<path>` therefore errored. It is retained as invalid-harness evidence and is not counted as the final Linux gate. The corrected Git checkout run had two failures:

1. `tests/test_generic_syntax_ir_verifier.py::test_native_verifier_differential_matrix_is_immutable_and_repeatable`: case 1 (`branch_program`) produced hosted value `100080774`, indicating rejection with verifier diagnostic 8 where the test's valid-case set expects acceptance. The verifier's opcode-shape path rejects this case. This is a real semantic test failure; it was not changed or hidden.
2. `tests/test_s3bench_cross_language.py::test_available_external_toolchains_match_one_checksum`: Zig failed with `NoSpaceLeft`. The guest root filesystem was 100% full (`/dev/sda2`, 25 GiB); `/tmp` still had space. A focused rerun with `ZIG_GLOBAL_CACHE_DIR` and `ZIG_LOCAL_CACHE_DIR` redirected to `/tmp` passed (1 passed, exit 0), confirming an environment-specific cache-capacity cause for this failure. This focused result does not convert the full-suite result to PASS.

Windows fixture root cause was proven as CRLF checkout conversion under `core.autocrlf=true`: the tracked fixture is 7,483 bytes with one LF and SHA-256 `daf23bc747d7d483391efad709b47ead8854bf2f70405829b2833cd0fee2a924`; the Windows checkout had one CRLF, 7,484 bytes, and SHA-256 `afb74dc054c8eabed4faaec1312aba07c3aea6cd2e2d6220173644a01363f54b`. A narrowly scoped `.gitattributes` rule pins that fixture to LF. A further `-text` rule preserves the raw bytes of the four frozen `.s3` source modules; the working source bytes were not normalized. No broad line-ending conversion was made.

## Final Status

```text
MAIN_BASE=5b4b8f12dc9aea94fab751136d98112a6e5c0098
BRANCH=feat/s3-1.13-selfhost-compiler-composition
FINAL_TESTED_CANDIDATE_HEAD=1487eb15f9ca151550861a4772f76509403e32f6
FINAL_SOURCE_SHA256=894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c
FINAL_SOURCE_BYTES=139740
SOURCE_PROVENANCE=PASS
SOURCE_VERSIONED=YES
SEMANTIC_REPRODUCIBILITY=PASS
ARTIFACT_BIT_REPRODUCIBILITY=UNRESOLVED
WINDOWS_FULL_SUITE=PASS
LINUX_FULL_SUITE=FAIL
COMPILEALL=PASS
DIFF_CHECK=PASS
SECRET_SCAN=PASS
FIRST_REAL_STAGE1_COMPILER_ARTIFACT=PROVISIONAL
FULL_SELFHOST=NO
STAGE2=NO
STAGE3=NO
DEFAULT_COMPILER=PYTHON
STAGE1=EXPERIMENTAL
PR=https://github.com/SamDevlab/S3/pull/327
PR_STATE=OPEN
PR_DRAFT=YES
PR_MERGEABLE_AT_INITIAL_PUBLICATION=MERGEABLE
PR_CHECKS_AT_INITIAL_PUBLICATION=4_PASS_8_PENDING_0_FAIL
MERGE_PERFORMED=NO
READY_FOR_REVIEW_AUTOMATICALLY_SET=NO
RELEASE_OR_TAG=NO
S3_1_14_STARTED=NO
```

Draft PR review is permitted by the campaign's minimum gate (recovered source plus semantic reproducibility), but this report explicitly leaves the Linux suite and independent artifact bit-rebuild unresolved. PR #327 was observed OPEN, Draft, and GitHub `MERGEABLE` at creation; its initial check snapshot was 4 passed, 8 pending, 0 failed. No check was treated as complete while pending. Do not mark Ready or merge. Stop for human review of this recovered Stage1 candidate and the verifier finding.
