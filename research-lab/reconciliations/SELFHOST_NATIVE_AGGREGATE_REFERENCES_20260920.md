# SELFHOST Native Aggregate References Reconciliation

## Provenance

```text
production_repository=SamDevlab/S3
base_pr=307
base_head=86dccea0d1e1499578005f7e3f89a46fd3afd2ed
campaign_branch=feat/s3-native-aggregate-references
functional_head=fd4cf580e61cd82b6c49425d0ee9d34d3573de8b
final_branch_head=59a27730bd6dd9ba3526fed160182dee8054d1d9
draft_pr=308
draft_pr_base=feat/s3-native-indexed-data
merged=no
```

## Question

Can a native aggregate cross a function boundary with explicit ownership and
lifetime without adding a new general ownership system, and is a read-only
borrow sufficient for a useful numeric workload?

## Evidence

The campaign added a bounded aggregate-reference representation for known
record types. A caller-owned `NativeIndexedValue` can be borrowed as one
immutable aggregate value for one call. The IR carries the aggregate identity,
record field paths, and the reference parameter metadata. The verifier checks
record identity and field layout. The emulator aliases the existing frame
cells rather than copying a host list. The semantic analyzer rejects mutable
aggregate references and aggregate-return escape paths.

The following evidence passed on the hosted S3 IR path:

```text
aggregate reference across function boundary=PASS
owner remains usable after call=PASS
two read-only borrows for SSD=PASS
i64 indexed execution=PASS
f64 indexed execution=PASS
bounds through reference=PASS
SSD [1,2,3] versus [2,4,6]=14.0 PASS
```

The first full suite was run exactly once at functional HEAD `fd4cf580`. It
ended with exit 1 because three exact-enum tests had not yet listed the new
aggregate opcodes. Those contracts were corrected in a test-only follow-up
commit `59a27730`; targeted affected tests, compileall and diff-check then
passed. The full suite was not rerun.

## Architectural result

The selected model is the minimum safe capability for this workload:

```text
owner=caller/local aggregate
borrower=callee
borrow_start=address-of at call
borrow_end=call return
borrow_escape=no
aggregate_mutation=no
aggregate_return=deferred
ownership_transfer=deferred
```

This is not a general borrow checker, garbage collector, object runtime, or
payload-plus-length fake ABI. It reuses existing typed vector payload and
bounds behavior while making the aggregate identity explicit at the semantic,
IR, verifier, lowering and emulator layers.

## First real blocker after SSD

The SSD workload passes, but RMSD is blocked by the absence of a qualified
`sqrt` primitive. Repository inspection found no existing semantic builtin,
IR opcode, runtime helper, libm path, or backend implementation. No Python
math fallback or ad hoc math library was added. Linux x86-64 aggregate
emission is also deferred because the new `TAGG*` assembly surface is not
implemented by the x86 emitter.

```text
NATIVE_MATH_PRIMITIVE_CONTRACT=OPEN
RMSD=BLOCKED
NATIVE_LINUX_AGGREGATE_EMISSION=DEFERRED
```

The next safe design decision is a minimal f64 sqrt contract under the
existing numeric comparison policy, followed by a separate native emitter
qualification. Do not promote this negative result to a durable theorem until
the implementation and evidence are independently reviewed.

## Knowledge disposition

Strengthens IC-003, IC-005, IC-008, IC-012, IC-015 and IC-016. IC-014 remains
unchanged. The bounded result supports the research direction that semantic
aggregate identity, legal representation and target realization must remain
separate, and that a workload-driven read-only borrow can avoid unnecessary
mutable ownership machinery. It does not establish full self-hosting, Linux
native aggregate ABI, sqrt, RMSD, or performance.

```text
S3_BENCHMARKS_CHANGED=NO
BIOLAB_REPOSITORY_CHANGED=NO
SHUTDOWN=NO
```
