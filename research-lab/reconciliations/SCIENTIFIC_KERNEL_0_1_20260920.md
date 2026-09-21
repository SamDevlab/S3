# Scientific kernel 0.1 reconciliation

Date: 2026-09-20
Production branch: `feat/s3-scientific-kernel-rmsd-v01`
PR: #309 (Draft)
Base PR: #308

## Result

The campaign began from the exact PR308 documentation head
`db0f6b1533938c925daa603209d76d94bbe72485`. The inherited corrected-state
full suite was run once before implementation and passed with exit 0. The
production implementation was limited to the existing dynamic CALL contract,
the existing f64 scalar/vector/reference machinery, and one SSE2 runtime
helper. No new scientific value representation and no new IR opcode were
introduced.

```text
FUNCTIONAL_HEAD=e07d0b5464bf472b2ca18993f3e196a234ff0fc5
DIRECT_F64_VECTOR_SSD_HOSTED=PASS_14_0
SQRT_HOSTED=PASS
SQRT_IEEE_EDGE_CASES=PASS
RMSD_HOSTED=PASS_SQRT_14_OVER_3
LINUX_X86_64_NATIVE=PASS
NATIVE_RESULT=program returned: -1
FULL_SUITE_FINAL=PASS
FULL_SUITE_FINAL_EXIT=0
BENCHMARK=NOT_RUN
```

The Linux proof used the configured VM and the same published candidate
commit. The native canary returned a ternary true result after executing the
direct vector SSD, division, and SSE2 square root path. The native runtime
does not claim decimal f64 entry output; the canary compares the f64 RMSD
inside S3 and returns `trit`.

## Architectural conclusion

The reuse audit found no need for `NativeIndexedValue`, new TAGG lowering, or
a new math opcode for this slice. `f64_vector_len/get`, borrowed references,
while-loop lowering, f64 arithmetic, dynamic `CALL`, and the existing x86
runtime were sufficient. `sqrt` was genuinely missing and is now an explicit
f64 dynamic builtin with one SSE2 implementation. RMSD remains a source-level
composition rather than a privileged runtime primitive.

This is a correctness and native-capability checkpoint, not a benchmark or
release claim. S3-Benchmarks and Biolab were unchanged. PR #309 remains Draft
and must not be merged by this reconciliation.
