# Actual Stage1 compiler seed

This report records the first executable compiler seed built from S3 source.
It does not change the historical M3.00 certification in PR #267 and does not
claim complete self-hosting.

## Boundary

The canonical source is `selfhost/compiler/s3c_stage1.s3`. Python Stage0 may
compile that source into Linux x86-64 assembly during the build. The resulting
process contains the compiler logic written in S3. The only host boundary is
`selfhost/compiler/stage1_host_io.c`, which provides a fixed 16,384-byte input
buffer, byte reads, byte writes to stdout/stderr, and process exit through raw
Linux syscalls. It does not tokenize, parse, resolve, lower, verify, or emit
assembly decisions.

The generated Stage1 process accepts this bounded source subset:

```text
fn main() -> tryte:
    return <signed decimal tryte>
```

It validates the complete input, parses the signed value, and emits real GNU
Intel-syntax assembly for a process that exits with that value. The emitted
assembly can be assembled and linked independently of Python. Invalid input
produces a deterministic S3-owned diagnostic and a non-zero process status.

## Current data flow

```text
host read bytes
  -> S3 byte scanner and grammar checks
  -> S3 signed decimal semantic/range validation
  -> S3 assembly byte emission
  -> host write bytes / exit
```

This is a real, deliberately small compiler, not a checksum or candidate
wrapper. It is not yet a general lexer/token store, AST, canonical IR,
multi-function compiler, module compiler, or full verifier. The gap matrix
records those boundaries without promoting the older differential components.

## Native qualification

The Windows checkout can validate Stage0 parsing and native assembly emission.
Native process construction and execution require a Linux x86-64 toolchain.
The focused native tests are therefore skipped on Windows and are not counted
as passed. A Linux run must build the process, compile the emitted trivial
assembly, execute it, exercise the corpus, reject invalid input, and attempt
the canonical source self-compile before Stage1 can be promoted.

## Non-goals

- no Stage2 or Stage3 marker is created;
- no Python runtime is available to the Stage1 process;
- no production compiler path is replaced;
- no benchmark or performance claim is made;
- no Docker dependency is introduced.
