# Stage 05 — Calls, call dataflow, arrays/indexing: close S3

## Goal

Implement complete ordered call dataflow plus fixed-array/index semantics required by canonical Stage1.

## Required calls

- zero-argument call;
- one/multiple arguments;
- nested call;
- call result reused by another instruction;
- internal function resolution;
- foreign function resolution/signature;
- ordered A edges;
- call R result edges;
- unresolved callee fails closed.

## Required array/index support

- fixed local array identity/storage;
- index value as a semantic operand;
- load from index;
- store to index if canonical Stage1 uses it;
- bounds semantics consistent with existing language/toolchain behavior.

## Capacity policy

Use measured call-argument peaks. Preserve existing call-pool evidence as provenance, but do not blindly reuse historical source-specific capacity if the candidate source changed.

## Required fixtures

```text
f()
f(a)
f(a,b)
f(g(a))
result = f(a)
foreign_call(a,b)
array[index]
array[index] = value   (if language/canonical source requires it)
call inside loop/control flow
```

## Exit gate

```text
S1=PASS
S2=PASS
S3_CALL_DATAFLOW=PASS
CALL_ARGUMENT_ORDER=PASS
INTERNAL_CALL_RESOLUTION=PASS
FOREIGN_CALL_RESOLUTION=PASS
ARRAY_INDEX_REQUIRED_SUBSET=PASS
```

S4/S5 may still be blocked. Re-check control before Stage 06.
