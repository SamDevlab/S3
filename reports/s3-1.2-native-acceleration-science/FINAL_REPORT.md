# S3 1.2 Native Acceleration and Scientific Expansion

## Result

The campaign integrates the selected historical P2 exact-segment accounting
candidate on the post-#313 baseline and adds a reusable, source-composed
scientific numeric module. `PER_INSTRUCTION` remains the default;
`EXACT_SEGMENT` is an explicit x86-64 backend mode. No syntax, IR, Assembly,
diagnostic, or stable-version format changed.

The scientific module `s3.v1.science` provides sum, dot product, mean,
population variance, squared distance, Euclidean distance, L2 norm, and RMSD.
Operations are composed from existing vector, reference, loop, f64, and sqrt
features. The binary operations use a status/value result for mismatched
lengths; the documented empty-input and IEEE-754 behavior is covered by tests.

## Provenance

```text
EXPECTED_BASE=e84281c4bfd6955ff7a4ba96b6922687eea51622
ACTUAL_BASE=e84281c4bfd6955ff7a4ba96b6922687eea51622
BRANCH=feat/s3-1.2-native-acceleration-science
FUNCTIONAL_SOURCE_FREEZE=7ae48ce88b7ca8648feea7a79674f8cc46edb9a8
FUNCTIONAL_SOURCE_TREE=e548d623311fedaa86c8f3261c3e1f7305b5f504
POST_FREEZE_BENCHMARK_HARNESS_COMMIT=e494c20b871a2f715fb116e0d29075f7c67e00b4
```

The post-freeze commit changes only the benchmark fingerprinting tool and its
focused regression test. It replaces use of the restricted Assembly text
adapter with a deterministic structural fingerprint of the immutable
`AssemblyProgram`, allowing workloads containing `TMUL` to be characterized.
It does not change compiler, optimizer, standard-library, runtime, or backend
behavior. The harness regression test passed separately and is not included in
the full-suite counts below.

P2 provenance:

```text
P2_SELECTED_SOURCE=1a76e341098b54a639fec22eecea362cc243c46f
P2_MAINLINE_PORT=9b16de03
P2_EXECUTABLE_EQUIVALENCE=YES
P2H_PORTED=NO
HISTORICAL_P2_EVIDENCE_REUSED=YES
DEFAULT_MODE=PER_INSTRUCTION
```

The ported backend modules match the selected P2 candidate; the test import
was adapted to the exported mode enum. The rejected P2H variant was not
ported. Existing format versions and the public `v1.0.0` stable baseline are
unchanged. The Python reference compiler remains authoritative; this campaign
makes no full-self-hosting claim.

## Validation

Focused Linux x86-64 validation on the source freeze passed: 83 tests across
the exact-segment accounting, scientific kernels, M1.44 standard library,
instruction limits, numeric native integration, and register-allocation
integration selections. The selected cases exercised hosted and native
correctness. The benchmark fingerprint regression passed separately (1/1).
The corresponding Windows focused selection passed with native-only skips as
expected. `python -m compileall bootstrap tests tools` and `git diff --check`
passed after the harness correction.

The valid final full suite ran on Linux x86-64 against the exact functional
source freeze and tree:

```text
FULL_SUITE_HEAD=7ae48ce88b7ca8648feea7a79674f8cc46edb9a8
FULL_SUITE_TREE=e548d623311fedaa86c8f3261c3e1f7305b5f504
OS=Linux 7.0.0-31-generic
ARCH=x86_64
PYTHON=3.14.4
PYTEST=9.1.1
GCC=15.2.0
ZIG=0.14.1
AS=2.46
LD=2.46
PASSED=4379
SKIPPED=1
FAILED=0
SUBTESTS_PASSED=572
ELAPSED_SECONDS=3918.79
EXIT=0
TRANSCRIPT=full-suite-linux-x86_64-gitbundle.txt
TRANSCRIPT_SHA256=617746ee76807f146b84d10a742b96ec19c4ea47a5a92b022a2d7f51df1e54b6
```

An earlier attempt from a source archive lacked `.git` metadata, causing
Git-backed golden checks to fail, and hit a full-root-filesystem Zig cache
failure. It is preserved, not overwritten, and is not counted as a valid
final result. Its incorrect manually recorded tree hash is reconciled in
[`full-suite-linux-x86_64-correction.md`](full-suite-linux-x86_64-correction.md).

## Native characterization

The first benchmark invocation stopped before producing native binaries or
timing samples because the restricted text adapter rejected the workload's
`TMUL` opcode. The harness correction above addressed only that fingerprint
path; the successful measurement below is the sole run with timing samples.

The benchmark used the same O1 `AssemblyProgram` per workload, 64-element
vectors, 500 kernel calls per process, two warmups, and nine counterbalanced
paired samples per mode. Only the instruction accounting mode changed. Each
native process was correctness-checked before timing. This is a small
same-host characterization, not a general performance guarantee.

| Kernel | PER median (ns) | EXACT median (ns) | Paired speedup | `.text` PER (B) | `.text` EXACT (B) | Delta |
|---|---:|---:|---:|---:|---:|---:|
| RMSD | 3,704,454 | 1,672,524 | 2.315x | 68,898 | 104,511 | +35,613 (+51.69%) |
| DOT | 3,199,031 | 1,371,249 | 2.259x | 68,898 | 104,511 | +35,613 (+51.69%) |
| VARIANCE | 5,452,507 | 2,602,951 | 2.095x | 68,722 | 104,214 | +35,492 (+51.65%) |

Raw sample sets, hashes, toolchain identity, and code sizes are in
[`scientific-budget-benchmark.json`](scientific-budget-benchmark.json);
the command's complete JSON output is preserved in
[`scientific-budget-benchmark-stdout.json`](scientific-budget-benchmark-stdout.json).
The native outputs matched their expected accumulated results in both modes.

The observed exact-segment speedup is material on these three kernels, while
the roughly 52% `.text` growth is also material. The workloads share one VM and
are intentionally narrow; they do not establish a universal benefit or an
acceptable size/performance tradeoff for representative application mixes.
Recommendation: `KEEP_PER_INSTRUCTION_DEFAULT`. Revisit only with broader
representative workloads and an explicit default-change decision. No default
switch was made.

## Documentation and delivery

The scientific and instruction-budget contracts are documented in
`docs/spec/scientific-numeric-foundation-v1.md` and
`docs/spec/x86_64-instruction-budget-v1.md`; README and ACTIVE_TRACK were
updated. A focused documentation-debt scan found no remaining current claim
that P2 is in `main` or that the default changed. Historical documents were
left intact.

GitHub Actions is blocked before workflow steps by the existing billing/quota
condition. No workflow was changed and no CI rerun was attempted. This report
does not treat the local Linux evidence as GitHub CI green.

```text
VALIDATION_MODE=LOCAL
GITHUB_ACTIONS_STATUS=BLOCKED_BY_BILLING_OR_QUOTA
CI_RERUN_ATTEMPTED=NO
WORKFLOW_CHANGED=NO
P2_DEFAULT_SWITCHED=NO
PR_MERGED=NO
NEW_TAG=NO
NEW_RELEASE=NO
PYPI_PUBLISHED=NO
```

The branch is submitted as a Draft PR for human merge review. Follow-ups are
SIMD/vectorization, reduction code generation, broader scientific kernels,
ARM64 qualification, and a separate decision on the P2 default. None is part
of this campaign.
