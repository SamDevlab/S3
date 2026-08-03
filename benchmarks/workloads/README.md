# s3bench Workload Corpus

Status: IMPLEMENTED - NOT BENCHMARKED UNTIL CONSOLIDATED VALIDATION

Every workload has a stable ID and independent `1.0.0` workload version in the
`s3bench-1.0.0.json` manifest. Inputs are deterministic, local, bounded, and
network-free. Workloads do not read clocks, generate random input, or perform
output inside an in-process kernel region.

## Portable Suite

| Benchmark ID | Input | Checksum | Timed region |
| --- | --- | ---: | --- |
| `runtime.scalar.accumulate.v1` | fixed scalar tuple | 42 | signed accumulation |
| `runtime.scalar.branch.v1` | two positive states | 1 | comparisons and branch state machine |
| `runtime.call.chain.v1` | bounded depth five, twice | 10 | nested scalar calls |
| `runtime.recursion.bounded.v1` | Fibonacci 10 | 55 | recursive kernel |
| `runtime.array.sum.tryte.v1` | three trytes | 60 | initialization, traversal, sum |
| `runtime.array.copy.tryte.v1` | five trytes | 15 | copy-by-value, return, sum |
| `runtime.text.scan.v1` | 21 ASCII identifier units | 21 | classification scan |

The current S3 text source resolves a static value at compile time. It is
preserved for compiler/representation evidence and must not be ranked as an
equivalent dynamic native scan without a compatible timed region.

## S3-Specific Engineering Suite

| Benchmark ID | Input | Checksum | Timed region |
| --- | --- | ---: | --- |
| `runtime.aggregate.record.return.v1` | width-two record | 10 | result transfer and full-cell reduction |
| `runtime.aggregate.sret.width3.v1` | nested width-three record | 7 | nested result transfer and reduction |
| `runtime.aggregate.enum.match.v1` | ok/error enum values | 4 | construction, transfer, match, payload use |
| `frontend.tokenizer.valid.v1` | Assembly 0.6 artifact | 157 | incremental tokens through end |
| `frontend.parser.valid.v1` | Assembly 0.6 artifact | 157 | parser events through end |
| `frontend.parser.invalid.v1` | unsupported version | 4 | structured failure path |
| `frontend.candidate.valid.v1` | Assembly 0.6 artifact | 69 | composed structural summary |
| `frontend.candidate.invalid.v1` | unsupported version | 4 | composed structured failure |
| `compiler.end_to_end.v1` | optimizer stress source | 0 | load through Assembly generation |

Tokenizer, parser, frontend, hidden result transport, and compiler-pipeline
cases are S3 engineering evidence. They are not placed in a cross-language
ranking.

## Sizes And Modes

S3 build artifacts record source bytes, serialized IR bytes, Assembly bytes,
function count, and instruction count. Native builds additionally record GNU
assembly and ELF bytes when Linux x86-64 is available. O0/O1 and
emulator/native are separate manifest cases; unsupported execution remains
explicitly unavailable.

The 0.8 E2 baseline is immutable historical evidence. It lacks workload
versions, raw timing samples, and complete environment metadata, so the 1.18
loader classifies timing comparison as `NOT_COMPARABLE` by default.
