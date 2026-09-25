# S3 1.3 Scientific Compute Engine

**Status:** implementation and Linux x86-64 validation complete; human review pending in one Draft PR. No merge, release, tag, or PyPI publication is included.

## 1. Delivered

The campaign extends the versioned `s3.v1.science` source library, adds three deterministic multi-size workloads to the existing `s3bench` corpus, adds conservative O1 loop-invariant vector-length hoisting and direct native lowering for vector length/access, and exposes `LOOP_HYBRID` as an explicit instruction-budget mode. Public source syntax 0.6, IR 0.6.0, Assembly 0.6.0, diagnostic schema 1.0.0, and the Python reference compiler remain unchanged.

New public scientific functions are `sum_squares`, `sum_abs`, `l1_norm`, `min`, `max`, `max_abs`, `sum_squared_difference`, `mae`, `mse`, `rmse`, `standard_deviation`, `covariance`, `correlation`, and `cosine_similarity`. Existing `sum`, `dot`, `mean`, `variance`, `squared_distance`, `distance`, `l2_norm`, and `rmsd` remain. `F64Result` expresses empty-input and incompatible-length outcomes for result-bearing operations; existing scalar `mean`/`variance` empty-input behavior is preserved. The implementations are source-composed; no scientific opcode family was added.

The scientific corpus contains:

| Workload | Stable ID | Vector lengths | Kernel calls | Total elements processed | Correct checksum |
|---|---|---:|---:|---:|---:|
| Structural comparison (computationally inspired; no biochemical-validity claim) | `science.structural-comparison.v1` | 64, 256, 1,024, 8,192 | 8 | 85,824 | 48,684 |
| Statistics matrix | `science.statistics-matrix.v1` | 64, 256, 1,024, 8,192 | 20 | 143,040 | 19,916 |
| Similarity and distance | `science.similarity-distance.v1` | 64, 256, 1,024, 8,192 | 24 | 76,288 | 29,356 |

Counts are taken from the versioned manifest. `total_elements_processed` is traversal accounting and is not inferred as `kernel_calls × vector_length`.

## 2. Compiler and native behavior

- **Loop analysis / LICM:** O1 hoists the read-only `f64_vector_len` builtin out of eligible canonical loops when the preheader and loop invariance are unambiguous. Unknown and mutating calls remain conservative barriers. This is a real general optimizer transform, but not a general induction-variable or reduction recognizer.
- **Vector access:** native lowering directly implements vector length and retains checked semantics for vector get. The call/helper route is avoided for those builtins; bounds checks are not removed.
- **Bounds-check elimination:** not implemented. No proof-based BCE is claimed.
- **Address strength reduction:** not implemented; no internal cursor/stride transformation is claimed.
- **Register allocation:** the campaign uses the existing allocator/backend facilities where configured; it does not introduce a second allocator or promote global defaults.
- **SIMD:** no vertical slice was safe under the current strict observable `f64` accumulation order. No reassociation or fast-math was enabled.
- **O0/O1 and native correctness:** included in focused and full validation; exact evidence is listed below.

## 3. Instruction-budget policy and code size

`PER_INSTRUCTION` remains the native default. `EXACT_SEGMENT` and `LOOP_HYBRID` are explicit alternatives. On the same structural-comparison workload, 15 samples after 3 warmups, pinned to one Linux CPU, all with checksum 48,684:

| Mode | Median process time | CV | p95 | Assembly source bytes | ELF bytes | ELF `.text` bytes |
|---|---:|---:|---:|---:|---:|---:|
| PER_INSTRUCTION | 12.277 ms | 4.70% | 13.394 ms | 2,098,335 | 851,896 | 207,999 |
| EXACT_SEGMENT | 5.106 ms | 12.05% | 6.594 ms | 3,195,726 | 1,276,400 | 323,268 |
| LOOP_HYBRID | 5.502 ms | 6.38% | 6.096 ms | 2,534,020 | 1,026,024 | 252,521 |

Relative to PER, EXACT's measured `.text` is **55.4% larger** and LOOP_HYBRID's is **21.4% larger**. The exact process median is 2.40× lower than PER and hybrid is 2.23× lower in this one composed workload, but sample variability and single-workload scope prohibit promotion. This campaign did not materially reduce exact-segment `.text` duplication; the expansion objective is unmet. The hybrid mode lowers code-size overhead versus EXACT but retains overhead and is not the default.

The prior PR #315 characterization reported approximately 51.6–51.7% `.text` growth on its narrower workloads. The current 55.4% measurement uses the expanded structural workload and is not a like-for-like historical regression measurement. `size -A` supplied actual ELF section sizes; assembly source length and total ELF size are reported separately and are not substitutes for `.text`.

## 4. BASE versus FINAL

The same structural workload and checksum (48,684) were measured on campaign BASE `2b4970256086e4dba0d498e36b0c42bcfc094ca0` and functional FINAL `adaff49a97c242cd00b15fee4ade565ed0768af2`, both O1, Linux x86-64, process scope, 15 samples and 3 warmups:

| Candidate | Median | CV | p95 | Assembly source bytes | ELF bytes |
|---|---:|---:|---:|---:|---:|
| BASE | 13.265 ms | 20.08% | 22.166 ms | 956,332 | 388,680 |
| FINAL | 13.001 ms | 9.60% | 15.794 ms | 2,098,335 | 851,896 |

The median is 1.98% lower for FINAL, but BASE's high variation and overlapping tail make this **NEUTRAL / INDETERMINATE**, not an established speedup. Assembly source grew 119.4% and total ELF bytes 119.2%. A BASE-versus-FINAL `.text` section measurement was not emitted by this protocol and is unavailable; no percentage is invented. Raw source JSONs omit the repository SHA; campaign base/final provenance is pinned above, while the final policy-mode JSON records the exact final SHA.

## 5. Cross-language evidence

The final stats/similarity cross-language run verified all expected checksums. C, Rust, Zig and Python entries use kernel scope; S3 entries measure whole-process execution (including process startup), so S3 medians are **not comparable** to their kernel timings and are not presented as speedups.

For similarity, C O2 measured 208.55 ms / 4,000 loops, Rust O2 245.07 ms / 5,000 loops, Zig ReleaseFast 207.46 ms / 4,000 loops, and Python reference 272.77 ms / 64 loops. For statistics, C O2 measured 232.13 ms / 3,000 loops, Rust O2 224.12 ms / 3,000 loops, Zig ReleaseFast 227.93 ms / 3,000 loops, and Python reference 201.08 ms / 48 loops. The normalized work is defined by each adapter; the raw dataset is authoritative. Rust similarity CV was 27.84%, so its single ratio is noisy. The cross-language evidence shows the new workloads are portable and correct, not that S3 is as fast as these kernel-only implementations.

## 6. Validation and provenance

- Functional source freeze: `adaff49a97c242cd00b15fee4ade565ed0768af2`; tree `0836f9d8b178f536493202ce0631e7731b6b6acf`.
- Linux focused budget-routing/native selection after the final functional fix: 26 passed.
- Full Linux x86-64 suite, exact freeze: 4,399 passed, 1 skipped, 0 failed, exit 0; 4,400 collected; 4,203 seconds. Transcript SHA-256: `f675f50d18417613e8ef8ee12e9a3479c96ee7e55a92dc07c4d6de95941ad0aa`.
- `s3bench` final scientific checksum verification: 33/33. First verify attempt had 4 Zig build failures due to VM root filesystem exhaustion (`NoSpaceLeft`), with the other 29 checksums verified. No files were deleted. The same four Zig configurations were rerun with Zig caches redirected to available temporary storage and all four passed. The initial JSON and retry JSONs are preserved separately.
- `compileall` and `git diff --check`: PASS on frozen source; the final subsequent edits are documentation/evidence only.
- Environment: controlled Linux x86-64, Python 3.14.4, pytest 9.1.1, GCC/cc 15.2.0, Rust 1.93.1, Zig 0.14.1; 3 logical CPUs and 8,634,437,632 bytes reported memory.
- No GitHub workflow was modified. GitHub Actions billing/runner provisioning remains an external infrastructure limitation tracked by issue #284; a local Linux pass is not GitHub CI green.

Raw inputs, failed-attempt provenance, retry outputs, timing samples, suite transcript and status are kept beside this report. `science-verify-final-8199de31.json` is an earlier-candidate historical artifact, not evidence for the final freeze. The final 33/33 total is reconciled only from the exact-`adaff49` first-pass JSON plus the two exact-`adaff49` Zig retry JSONs. See `evidence-hashes.txt`, `benchmark-results.md`, `benchmark-results.json`, `cross-language-results.json`, `environment.json` and `focused-validation.txt`.

## 7. Promotion decisions

| Change | Decision |
|---|---|
| Read-only vector-length LICM in eligible O1 loops | `PROMOTED_TO_O1` |
| Direct native vector length and checked vector-get lowering | `NATIVE_DEFAULT` for the supported lowering path; checks preserved |
| EXACT_SEGMENT | `OPT_IN`; not default due to material `.text` growth and workload-limited timing |
| LOOP_HYBRID | `OPT_IN`; smaller `.text` than EXACT in this case, still larger than PER |
| General BCE, address strength reduction, SIMD | `REJECTED/NOT_IMPLEMENTED` in this campaign; current evidence does not justify relaxing safety or FP order |
| PER_INSTRUCTION | remains `NATIVE_DEFAULT` |

## 8. Remaining limits and next expansion

The direct scientific evidence supports broader native scientific coverage, but not a general speedup over the pre-campaign compiler. The most consequential measured tradeoff is that faster explicit accounting modes enlarge native text, and the exact-mode size tax is larger on this expanded workload than PR #315's earlier characterization. The next grounded optimization is to reduce exact-budget cold-path/text duplication while preserving the precise logical instruction that exhausts the budget, followed by repeated multi-workload timing and `.text` measurement. In parallel, a proven bounds-check-elimination slice for the canonical `i=0; i<len(v); i++` loop is a sensible compiler step, but should be separately proven with negative cases. SIMD should wait for an explicit semantic contract for strict reductions rather than silently reassociating `f64` operations.

## 9. Historical PR provenance

PR #315 is merged and supplies the integrated 1.2 foundation. Historical Drafts #302–#312 are not prerequisites for this campaign's current source stack; the cumulative integration through #313/#315 supersedes their implementation role. PR #295 is separate 1.1.0 release preparation and is not part of this campaign. None was changed or closed here.

## 10. Delivery state

This report describes the frozen functional candidate plus later report-only documentation/evidence. `SOURCE_CHANGED_AFTER_FREEZE=NO`. The campaign is submitted for human review in one Draft PR only. Merge, release, tag, PyPI publication and changes to `v1.0.0` are explicitly out of scope.
