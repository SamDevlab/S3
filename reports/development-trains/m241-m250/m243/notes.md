# M2.43 Linux x86-64 Native Conformance Closure

## WHY_NOW

The train has stable workspace and LSP semantics. Native correctness must now
be certified across the current Linux x86-64 execution boundary before the
HTTP/2 and registry milestones add more cross-layer behavior.

## CONTRACT

The conformance corpus compares the hosted emulator with real Linux x86-64
executables at O0 and O1, with register allocation both disabled and enabled.
It covers ordinary calls and returns, System V argument stack use, recursion,
reference-based array mutation, and representative example programs. The
Compact EA experimental mode is explicitly `off`; TMOV remains part of the
checked reference/memory path. This is a correctness contract only and makes
no performance claim.

## IMPLEMENTATION_SUMMARY

- Added a bounded Linux x86-64 O0/O1 conformance matrix.
- Covered both backend register-allocation modes without changing production
  lowering behavior.
- Added explicit Compact EA-off and TMOV regression coverage.
- Added M2.43 T2/T3 impact and shard metadata.

## TEST_EVIDENCE

The authoritative Linux result was recorded on source lock
`d15dd94cf0617687b0a5fc9997247ca2c74a604f`.

- compileall: PASS
- focused native conformance: 25 passed, exit 0
- T2 milestone: 1 selected, 1 passed, exit 0
- T3 M2.43 shard: 1 selected, 1 passed, exit 0
- diff check: PASS

The Windows checkout skipped all 25 Linux-only cases by platform policy; it
did not count as native evidence.

## BENCHMARK_RELEVANCE

None. This milestone certifies native correctness and ABI behavior only.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

The corpus is intentionally bounded and representative; it is not a claim
that every possible native program has been exhaustively enumerated.
