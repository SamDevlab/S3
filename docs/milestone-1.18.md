# Milestone 1.18 - S3 Runtime And Compiler Benchmark Corpus

Status: IMPLEMENTATION COMPLETE - BENCHMARK EXECUTION DEFERRED

## Contract

The 1.18 corpus provides stable workload IDs, independent versions, bounded
inputs, deterministic checksums, supported implementation/mode declarations,
timeouts, scale labels, and explicit timed regions. Source and fixture creation
is outside measured regions unless a process-level case explicitly includes it.

Every workload consumes its result. S3 aggregate cases reduce all relevant
result cells. There is no random input, clock access, network access, debug
logging, or workload output inside an in-process kernel.

## Coverage

The portable group covers scalar accumulation, comparisons/branches, shallow
calls, bounded recursion, fixed-array traversal, fixed-array copy-by-value, and
bounded ASCII classification. The S3-specific group covers record and enum
result groups, nested hidden-sret transport, tokenizer valid input, parser valid
and invalid paths, frontend-candidate valid and invalid paths, compiler
end-to-end work, and artifact metrics.

S3 cases explicitly enumerate emulator O0/O1 and native O0/O1. Missing native
support is unavailable rather than simulated. Python references are interpreted
evidence and are not merged into native rankings.

## Artifact Metrics

The S3 adapter records source bytes, serialized IR bytes, S3 Assembly bytes,
function count, instruction count, and, when built natively, GNU assembly and
ELF bytes. Size is reported independently and is not treated as speed.

## Historical Baseline

`benchmarks/baseline-0.8-e2.json` remains byte-for-byte historical. It has
deterministic structural value but lacks workload versions, raw timing samples,
timed-region identity, and complete environment metadata. The new loader marks
timing comparisons `NOT_COMPARABLE` unless later review proves a narrower match.

## Authored Coverage

Coverage checks manifest completeness, stable IDs and versions, checksum
presence, O0/O1 hosted parity, explicit native contracts, arrays, aggregates,
bounded text, tokenizer/parser/frontend checksums, invalid input, compiler
pipeline completion, artifact metrics, forbidden timed-region I/O, stable input
sizes, and historical classification.

CREATED - NOT EXECUTED UNTIL MILESTONE 1.19 IMPLEMENTATION COMPLETION
