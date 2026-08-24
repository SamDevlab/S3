# Actual Stage1 compiler seed

This report records the bounded Stage0-to-Stage1 compiler pipeline in
`selfhost/compiler/s3c_stage1.s3`. It does not change the M3.00 certification
and does not claim complete self-hosting.

## Boundary

Python Stage0 compiles the canonical S3 source into a static Linux x86-64
process. The resulting process contains the compiler logic written in S3.
The only host boundary is `selfhost/compiler/stage1_host_io.c`, which provides
a bounded 65,536-byte input buffer, byte reads, byte writes to stdout/stderr,
and process exit through raw Linux syscalls. It does not tokenize, parse,
resolve, lower, verify, or choose assembly on behalf of Stage1.

## Current pipeline

```text
host read bytes
  -> S3 token scanner and bounded token arrays
  -> S3 function-table parser
  -> S3 return-type and duplicate-name semantics
  -> S3 bounded return IR records
  -> S3 opcode/type verifier
  -> S3 simple-return assembly emitter
  -> host write bytes / exit
```

The canonical self-source was qualified on Linux x86-64 through lexing,
parsing, semantic analysis, IR construction, and verification. The IR audit
shows that it contains only one `OP_RETURN` record per parsed function, with no
function identity, body instructions, operands, calls, or CFG blocks. The
verified input is therefore insufficient for a general emitter to reconstruct
the compiler source. Stage1 returns `S3_STAGE1_EMITTER_BLOCKED`; the precise
blocker is `IR_SHAPE_LOSSY`, and Stage2 was not attempted.

The supported executable subset is:

```text
fn main() -> tryte:
    return <signed decimal tryte>
```

The signed values `0`, `7`, `8`, `180`, and `-1` produce distinct deterministic
assembly; the linked native executables exit `0`, `7`, `8`, `180`, and `255`
respectively. Invalid input produces `S3_STAGE1_ERROR`.

## Native qualification

The final qualification used the `s3-vm` Linux x86-64 guest with `/usr/bin/cc`.
The artifact is a static ELF64 executable without `PT_INTERP`; no WSL
distribution or Docker dependency was introduced. The artifact and assembly
hashes are recorded in `native-qualification.json` and `stage1-build.json`.

## Non-goals

- no Stage2 or Stage3 marker is created;
- no Python runtime is available to the Stage1 process;
- no production compiler path is replaced;
- no benchmark or performance claim is made;
- no Docker dependency is introduced.
