# Actual Stage1 compiler seed

This report records the bounded Stage0-to-Stage1 compiler pipeline in
`selfhost/compiler/s3c_stage1.s3`. It closes the former one-record-per-function
IR gap for the structural bootstrap subset without claiming complete
self-hosting or a general emitter.

## Boundary

Python Stage0 compiles the canonical S3 source into a static Linux x86-64
process. The resulting process contains the compiler logic written in S3.
The only host boundary is `selfhost/compiler/stage1_host_io.c`, which provides
a bounded 262,144-byte input window, byte reads, byte writes to stdout/stderr,
and process exit through raw Linux syscalls. It does not tokenize, parse,
resolve, lower, verify, or choose assembly on behalf of Stage1.

## Current pipeline

```text
host read bytes
  -> S3 token scanner and bounded token arrays
  -> S3 bounded function/signature and body event collection
  -> S3 semantic checks and deterministic event ledger
  -> bounded function/value/call/block/target IR lanes
  -> fail-closed IR verifier
  -> simple-return assembly emitter for the existing supported subset
  -> host write bytes / exit
```

The former audit remains in `self-source-ir-audit.json`. The new audit in
`self-source-ir-audit-v2.json` records 30 function records (25 local and 5
foreign), 325 blocks, 1212 event instructions, 926 values, 366 calls, 104
branches, 6 loops, and 103 returns for the current canonical source. Function
identity, foreign/local kind, event operands/offsets, call lanes, values, and
explicit control targets are represented and checked by the verifier.

This is a bounded structural event IR for the bootstrap source, not a claim
that every complete S3 AST feature is already typed and serializable. In
particular, independent parameter/local type and mutability tables and a
canonical IR byte digest remain follow-up work. The general emitter cannot yet
consume this IR and reports `S3_STAGE1_EMITTER_BLOCKED`; the next blocker is
`EMITTER_CAPABILITY`.

## Native qualification

The final qualification used the `s3-vm` Linux x86-64 guest with `/usr/bin/cc`.
Two builds of the same source produced identical artifact SHA-256
`41f4ac5dd17d042bb3f448f9c9878e6e52aae1ccf8d6ba793205e1a3b9121c7e` and
identical assembly SHA-256
`512044229ba5a4035c1d862ee167839e96e95a029556e01a6d97b26871d03be0`.
The artifact is a static ELF64 executable without `PT_INTERP`; no WSL
distribution or Docker dependency was introduced.

The supported simple-return corpus exits `0`, `7`, `8`, `180`, and `255` for
source values `0`, `7`, `8`, `180`, and `-1`. Invalid input produces
`S3_STAGE1_ERROR`.

## Non-goals

- no Stage2 or Stage3 marker is created;
- no Python runtime is available to the Stage1 process;
- no production compiler path is replaced;
- no benchmark or performance claim is made;
- no Docker dependency is introduced;
- no general Assembly emitter is implemented in this round.
