# Milestone 1.42 - Explicit Structured Result and Error Flow

Status: COMPLETE.

## Goal

Close one recoverable error vocabulary for S3 programs without exceptions,
implicit propagation, generic `Result<T,E>`, or a second ABI.

## Contract

- ADR-0030 explicit structured result and error flow;
- spec/structured-results-and-errors.md;
- existing fixed-layout payload enum and aggregate-result contracts;
- existing deterministic diagnostic and runtime trap taxonomy.

Recoverable outcomes are ordinary nominal enums with explicit success/error
variants and declared payloads. Callers use exhaustive `match` and propagate
variants explicitly. Language and runtime invariant violations remain semantic
diagnostics or deterministic traps.

## Evidence

The existing compiler path already provides parser, semantic layout, lowering,
IR grouped results, hosted execution, Assembly result groups, and native
aggregate return support. M1.42 adds focused proof for nested error context,
explicit propagation, deterministic IR/Assembly serialization, unchecked
scalar use rejection, and exhaustive matching.

## Verification gates

- focused M1.42 tests: PASS (4 tests);
- hosted O0/O1 structured result path: PASS;
- Linux x86-64 native O0/O1 path: PASS (24 in both modes);
- deterministic IR and Assembly serialization: PASS;
- compileall: PASS;
- full suite: terminal exit 0;
- no generic syntax, exception runtime, benchmark special case, or remote
  write introduced.

## Boundary

M1.42 is closed. M1.43 is the next milestone and owns scoped host resources
and capability enforcement. It must use explicit result values for recoverable
resource failures and must not reopen the result representation or introduce
exceptions.
