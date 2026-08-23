# S3 v3.00 Full Self-Hosting Roadmap

Status: development contract for the M2.71-M3.00 campaign.

This document defines what S3 must prove before the project may claim **full
self-hosting**. It intentionally distinguishes bounded S3-authored candidates
from a compiler that can rebuild itself without Python in the compiler path.

## Current baseline

At M2.70 the repository has a composed S3-authored bounded frontend candidate,
an explicit opt-in canary, and a fail-closed Python fallback. Python remains the
reference and default compiler path. M2.71 begins semantic self-hosting with a
bounded exact symbol-table kernel.

None of M2.71-M2.99, individually or collectively, may claim full self-hosting
unless the M3.00 gates below pass on one source-locked revision.

## Non-negotiable v3.00 definition

The v3.00 self-hosting claim requires a reproducible three-stage bootstrap:

```text
S3 compiler sources
       |
       | Stage 0: existing Python bootstrap compiler
       v
Stage 1 S3 compiler artifact
       |
       | Stage 1 compiles the same S3 compiler sources
       v
Stage 2 S3 compiler artifact
       |
       | Stage 2 compiles the same S3 compiler sources
       v
Stage 3 S3 compiler artifact
```

The test harness may launch processes, create temporary directories, and compare
artifacts. The **Stage 1 -> Stage 2** and **Stage 2 -> Stage 3** compilation
paths must not import, execute, or delegate compiler work to Python.

A successful M3.00 certification requires all of the following on the same
source lock:

- Stage 1 is produced from the canonical S3 compiler sources by the existing
  bootstrap compiler.
- Stage 1 successfully compiles the canonical S3 compiler sources into Stage 2.
- Stage 2 successfully compiles the canonical S3 compiler sources into Stage 3.
- Stage 2 and Stage 3 canonical compiler outputs are equivalent.
- Canonical equivalence uses exact bytes or a cryptographic digest of exact
  canonical bytes; modulo fingerprints are not accepted as final evidence.
- Stage 2 compiles a representative language corpus and the results match the
  reference correctness contract.
- Required diagnostics are produced by the S3 compiler path, not synthesized by
  a Python semantic adapter.
- Required IR/lowering/verifier work is performed by the S3 compiler path.
- Required assembly/object emission is performed by the S3 compiler path.
- The default `s3` compiler path can be switched to the certified S3 compiler
  with an explicit rollback path retained for the release transition.
- Global T4 passes on the source-locked M3.00 candidate.
- No benchmark or speed claim is inferred from the self-hosting claim.

`FULL_SELF_HOSTING=YES` is forbidden before every required gate above passes.

## Evidence rules

Every milestone keeps the existing evidence discipline:

- bounded scope stated explicitly;
- Python remains the reference/default until a later promotion gate says
  otherwise;
- missing provider/platform/CI evidence remains DEFERRED or NOT RUN, never PASS;
- no benchmark timing unless the milestone changes performance behavior;
- no global T4 on every small milestone;
- exact/canonical comparison preferred over small fingerprints;
- fail closed on unsupported inputs and differential mismatch;
- one integration train per ten-milestone block.

## M2.71-M2.80 — semantic self-hosting

### M2.71 — exact symbol table kernel

S3-authored bounded symbol insertion and exact lookup. Duplicate symbols and
invalid kinds fail closed. This milestone is already implemented as a Draft
candidate and still requires normal qualification.

### M2.72 — lexical and module name resolution

Add bounded scope ancestry and nearest-visible-declaration resolution. Preserve
shadowing semantics and reject malformed/cyclic scope graphs. Observable
results must be exact symbol/slot identities, not hashed names.

### M2.73 — scalar type checking

Add S3-authored checking for core scalar expressions, assignment compatibility,
comparisons, arithmetic and explicit conversion rules used by the compiler
subset.

### M2.74 — mutability, place and reference checks

Move the compiler subset's readable/writable/addressable/place decisions and
reference mutability checks into S3-authored semantic code with exact structured
results.

### M2.75 — function declarations and calls

Resolve bounded function signatures, argument arity/types and return types in
the S3 path. Reject duplicate functions and invalid calls deterministically.

### M2.76 — records, enums and fixed layouts

Move the fixed-layout semantic subset required by the self-hosted compiler into
S3, including deterministic record/enum layout identities.

### M2.77 — control-flow and return-path analysis

Implement bounded block termination, required-return analysis and unreachable
semantic classification required by compiler sources.

### M2.78 — composed semantic closure

Compose M2.71-M2.77 behind one canonical semantic input/output contract. Python
may act as the differential reference, but must not precompute semantic answers
for the S3 candidate.

### M2.79 — semantic canary

Add explicit opt-in semantic candidate routing with immediate fail-closed
fallback on candidate error, reference drift or canonical mismatch.

### M2.80 — semantic self-hosting checkpoint

Run a Level-C profile covering M2.71-M2.79. The checkpoint may declare
`S3_SEMANTIC_SELF_HOSTING_CANDIDATE=YES`; it may not declare full compiler
self-hosting.

## M2.81-M2.90 — IR, lowering and verifier self-hosting

### M2.81 — canonical S3 IR data model

Introduce the bounded S3-authored IR structures needed by compiler sources and a
canonical serializer suitable for exact comparison.

### M2.82 — expression lowering

Lower core scalar expressions and calls into canonical IR entirely inside the
S3 candidate.

### M2.83 — control-flow lowering

Lower branches, matches, loops and returns with deterministic block/temp IDs.

### M2.84 — aggregate lowering

Lower fixed arrays, records, enums and aggregate returns required by the
self-hosted compiler subset.

### M2.85 — ownership/reference lowering

Carry move/copy/reference semantics required by the compiler sources into IR
without Python-precomputed decisions.

### M2.86 — S3-authored IR verifier

Validate block structure, terminators, operand/result contracts and supported
SSA/IR invariants in the S3 path.

### M2.87 — canonical IR serialization

Produce versioned exact canonical bytes for differential and bootstrap
reproducibility evidence.

### M2.88 — composed lowering closure

Compose semantic input through lowering and verification into canonical IR
without Python transformations between S3 stages.

### M2.89 — lowering canary

Add explicit opt-in fail-closed routing for the composed S3 semantic/lowering
candidate.

### M2.90 — IR/lowering self-hosting checkpoint

Run Level-C over M2.81-M2.89 and record the exact subset capable of lowering the
canonical compiler sources.

## M2.91-M3.00 — emission, driver and bootstrap closure

### M2.91 — S3-authored Assembly IR emission

Render verified canonical IR into the supported S3 Assembly representation in
S3-authored code using deterministic ordering and exact text/byte evidence.

### M2.92 — Assembly verification closure

Compose the existing S3-authored Assembly tokenizer/parser work with the
emission path so emitted compiler output can be parsed and verified without a
Python Assembly parser in the compiler path.

### M2.93 — object/native emission boundary

Provide the deterministic backend boundary required for a standalone compiler
artifact. Any host linker/assembler invocation must be an explicit host tool
boundary, not hidden Python compiler logic.

### M2.94 — source/workspace loading in the S3 compiler path

Move canonical source discovery/loading, module ordering and workspace graph
construction needed by the compiler itself behind S3/host-service contracts.

### M2.95 — standalone compiler driver

Create a Stage-1-capable S3 compiler driver that accepts source/workspace input
and executes frontend -> semantics -> lowering -> verifier -> emission without
Python semantic/compiler delegation.

### M2.96 — compiler-source closure

Compile the canonical S3 compiler source tree with the standalone candidate.
Close any remaining language-feature gaps exposed by compiling the compiler
itself.

### M2.97 — Stage 1 -> Stage 2 bootstrap

Use the Stage 1 S3 compiler artifact to compile the same canonical compiler
sources into Stage 2. Python may orchestrate the test process only; it may not
perform compilation stages.

### M2.98 — Stage 2 -> Stage 3 reproducibility

Use Stage 2 to produce Stage 3 and compare Stage 2/Stage 3 canonical artifacts
with exact bytes or cryptographic digests of canonical bytes.

### M2.99 — promotion candidate and rollback boundary

Exercise the S3 compiler as a release candidate over the required corpus,
verify fail-closed rollback behavior, and prepare the default-path promotion.
No promotion is authorized if bootstrap reproducibility or correctness evidence
is incomplete.

### M3.00 — full self-hosting certification

Run the source-locked certification campaign containing:

1. Stage 0 -> Stage 1 bootstrap.
2. Stage 1 -> Stage 2 self-compilation.
3. Stage 2 -> Stage 3 self-compilation.
4. Stage 2/Stage 3 canonical equivalence.
5. required compiler-source and representative-corpus compilation.
6. required native/emulator correctness gates for supported release targets.
7. full global T4.
8. provenance report containing source SHA, compiler artifact digests, commands,
   environment classification and explicit skips/deferments.

Only after all required M3.00 gates pass may the project record:

```text
S3_FULL_SELF_HOSTING=YES
PYTHON_COMPILER_REQUIRED_FOR_NORMAL_BUILD=NO
STAGE2_STAGE3_REPRODUCIBLE=YES
M300_T4=PASS
```

Until then the strongest valid claim is the narrowest qualified candidate or
checkpoint reached by the train.
