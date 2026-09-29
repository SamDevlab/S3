# S3 1.13 Stage1 Composition Qualification

Status is local and uncommitted on `feat/s3-1.13-selfhost-compiler-composition`,
based on `5b4b8f12dc9aea94fab751136d98112a6e5c0098`. The original checkout was
not used. This report supplements the historical Gate Zero inventory and does
not rewrite its base-state findings.

## Result

```text
FIRST_REAL_STAGE1_COMPILER_ARTIFACT=YES
STAGE1_SUBSET=EXPERIMENTAL_I64_SOURCE_TO_S3_ASSEMBLY
CANONICAL_SELFHOST_IR=NativeIR
GENERIC_LOWERING=PASS
S3_VERIFIER_CONNECTED=PASS
S3_EMITTER=PASS
REAL_OUTPUT_SINK=PASS
STAGE1_COMPOSITION_ROOT=stage1_compile
HOST_SEMANTIC_FALLBACK=NO
HOST_LOWERING_FALLBACK=NO
HOST_EMITTER_FALLBACK=NO
FULL_SELFHOST=NO
STAGE2=NOT_ATTEMPTED
STAGE3=NOT_ATTEMPTED
CAMPAIGN_COMPLETE=NO
```

The Python Stage0 compiler built the candidate from S3 modules. Stage1 itself
scans source bytes, parses function/expression structure, registers functions,
lowers into `NativeIR`, calls the S3 verifier, emits S3 Assembly, and exposes
bytes only after the transactional OutputSink commit. Python remained the
oracle, build driver, and test harness; the package default remains Python.

Accepted subset: multiple same-program functions with `i64` parameters/results,
nonnegative literals, identifier reads, parentheses, `+`, `*`, immutable `i64`
locals, positional/nested/forward calls, and one final return per function.
Unsupported or invalid shapes fail closed. Limits remain source 4096 bytes,
1024 tokens, 16 functions/blocks, 512 NativeIR values/instructions, 64 total
formal parameters, 64 body statements per function, and 16384 output bytes.

## Frozen Candidate

```text
BRANCH=feat/s3-1.13-selfhost-compiler-composition
BASE=5b4b8f12dc9aea94fab751136d98112a6e5c0098
STAGE1_COMPILER_SHA256=894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c
STAGE1_COMPILER_BYTES=139740
STAGE1_SOURCE_FREEZE_TREE=4a5fc8f3ce57f66c35bc8610f3ec365e8390c5f16c0a5d08354e30fd50f93224
SOURCE_CHANGED_AFTER_FREEZE=NO
CANONICAL_SELFHOST_COMPILER_CHANGED=NO
```

The source-tree digest covers the four candidate modules: generic lexer/parser
state, verifier kernel, OutputSink, and `stage1_compiler_v1.s3`. Their individual
SHA-256 values are recorded in this report's qualification evidence and were
checked again on the Linux VM before native execution.

## Corpus And Artifact Evidence

Seven implementation fixtures and one source selected after the freeze were
accepted. Eight invalid/unsupported programs were rejected consistently with
the Python reference. No false accept, false reject, or valid-program result
mismatch was observed. The focused Stage1 file passed all 19 cases, including
the repeated-compilation determinism case and the static host-fallback guard.

The post-freeze unseen source is 180 ASCII bytes, SHA-256
`2cf533562f25a4d15c8d5aa33c3ba283024c605f539c58f6f38f4c003b27960e`. Stage1
produced a 591-byte S3 Assembly 0.6.0 artifact with SHA-256
`7d21e7c892255fb7a434c506115a74063c27c6524805827c2e68d34a36f6ee40`. The
artifact parsed and executed to 38, matching `run_source`. All eight artifact
records are in `STAGE1_ARTIFACT_MANIFEST.json`.

Repeated Stage1 compilation of the arithmetic-42 fixture produced identical
bytes. The evidence is content-based; the native harness uses a 46-bit dual
polynomial fingerprint plus artifact length/status, not a byte-for-byte native
stdout transfer. The hosted artifact bytes were independently parsed and
executed.

## Linux Native Qualification

The available VM was positively identified as Linux x86-64, Python 3.14.4,
with `/usr/bin/cc` (GCC 15.2.0). The exact frozen candidate module hashes were
verified after transfer. Stage0 built an ELF launcher that executes the same
Stage1 candidate on the unseen source. With an explicit bounded native logical
instruction limit of 100,000,000, the native Stage1 accepted and compiled the
source; its artifact fingerprint and length matched the already parsed and
executed hosted artifact. Thus Level A, Level B, and Level C were demonstrated
for the frozen subset. A preliminary ELF run at the default 100,000 limit
stopped at that configured limit in generic parser indentation scanning; no
source change was made for this resource-policy adjustment.

## Validation Gates

```text
FOCUSED_STAGE1=19 passed
FOCUSED_ADJACENT_GROUP=PASS
COMPILEALL_BOOTSTRAP_TESTS_TOOLS=PASS
DIFF_CHECK=PASS_AFTER_DOCUMENTATION_UPDATES
AI_CAPABILITIES_JSON=VALID
LINUX_NATIVE_UNSEEN_SOURCE=PASS
```

The one post-freeze full suite run on Windows terminated with exit 1 and five
failures, all in `tests/test_s3_16_public_dataset_agent_kernels.py`. Each
failed before its substantive test at the same pinned-fixture SHA assertion.
The manifest expects the Git blob SHA-256
`daf23bc747d7d483391efad709b47ead8854bf2f70405829b2833cd0fee2a924`; the
Windows worktree bytes hash to
`afb74dc054c8eabed4faaec1312aba07c3aea6cd2e2d6220173644a01363f54b` because
`core.autocrlf=true` converts the fixture's final LF to CRLF. Git reports both
fixture and manifest unchanged. A Linux focused run using the exact Git blob
passed (`1 passed`), confirming the checkout line-ending cause. Neither fixture
nor manifest was altered. The full-suite pass/skip totals were not retained in
the terminal capture and are intentionally not reconstructed or invented.

Consequently the compiler artifact is proven, but the repository-wide
regression gate is not green in this Windows checkout. No full-suite rerun was
started. The failure is independent of the S3 1.13 files, but the campaign is
not marked fully complete until the platform-sensitive test gate is resolved
and qualified under the campaign's one-run policy.

## Deferred Frontier And Actions

The Stage1 source (139740 bytes) exceeds its 4096-byte input bound and uses
language constructs outside the accepted subset. Self-emission is therefore
`DEFERRED`, not simulated. Stage2, Stage3, fixed point, benchmark, T4, PR,
commit, push, merge, release, tag, and default promotion were not performed.

```text
REFERENCE_COMPILER=PYTHON
STAGE1_S3_COMPILER=EXPERIMENTAL_SOURCE_TO_ARTIFACT_SUBSET
CURRENT_SELFHOST_FRONTIER=EXPAND_STAGE1_SUBSET_AND_BEGIN_BOUNDED_SELF_SOURCE_COMPILATION
S1_13_HUMAN_REVIEW=REQUIRED
STOP_HUMAN_GATE=REVIEW_S3_1_13_FIRST_REAL_STAGE1_COMPILER_ARTIFACT
```
