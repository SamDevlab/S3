# Benchmark Results — S3 1.3

All final workload checksums matched their expected values. Raw s3bench JSON is preserved next to this summary.

## BASE versus FINAL: structural comparison

O1, Linux x86-64, process scope, 3 warmups, 15 samples, checksum `48684`.

| Candidate | Median (ms) | CV | p95 (ms) | Assembly source (bytes) | ELF (bytes) |
|---|---:|---:|---:|---:|---:|
| BASE `2b497025` | 13.265 | 20.08% | 22.166 | 956,332 | 388,680 |
| FINAL `adaff49a` | 13.001 | 9.60% | 15.794 | 2,098,335 | 851,896 |

Median time changed by -1.98%, classified **NEUTRAL / INDETERMINATE** because the baseline CV is 20.08%. Assembly source grew 119.4%, total ELF 119.2%. BASE-versus-FINAL `.text` was unavailable from this measurement protocol.

## Instruction budget modes: same FINAL workload

| Mode | Median (ms) | CV | p95 (ms) | Assembly source (bytes) | ELF (bytes) | `.text` (bytes) |
|---|---:|---:|---:|---:|---:|---:|
| PER_INSTRUCTION | 12.277 | 4.70% | 13.394 | 2,098,335 | 851,896 | 207,999 |
| EXACT_SEGMENT | 5.106 | 12.05% | 6.594 | 3,195,726 | 1,276,400 | 323,268 |
| LOOP_HYBRID | 5.502 | 6.38% | 6.096 | 2,534,020 | 1,026,024 | 252,521 |

All three modes produced checksum `48684`. Exact median was 2.40× lower than PER in this single workload; hybrid was 2.23× lower. `.text` grew +55.4% for exact and +21.4% for hybrid versus PER. This does not justify default promotion or a general performance claim. `PER_INSTRUCTION` remains default.

## Workload matrix

| Stable ID | Lengths | Kernel calls | Total elements | Expected checksum |
|---|---|---:|---:|---:|
| `science.structural-comparison.v1` | 64, 256, 1,024, 8,192 | 8 | 85,824 | 48,684 |
| `science.statistics-matrix.v1` | 64, 256, 1,024, 8,192 | 20 | 143,040 | 19,916 |
| `science.similarity-distance.v1` | 64, 256, 1,024, 8,192 | 24 | 76,288 | 29,356 |

The aggregate manifest traversal counts are preserved exactly; they are not derived from call-count multiplication.
