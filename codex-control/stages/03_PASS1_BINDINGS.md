# Stage 03 — Pass 1: functions, signatures, and lexical bindings

## Goal

Create the candidate-only first semantic pass used by the Stage1 v2 lowerer.

Recommended candidate transform:

```text
tools/patch_stage1_semantic_port_v2.py
```

Generated source:

```text
.artifacts/s3c_stage1_semantic_v2.s3
```

## Required semantics

Collect deterministically:

- function IDs and exact ASCII name spans;
- internal vs foreign function kind;
- parameter count/order/type/name span;
- function result/return signature;
- locals and loop variables;
- lexical scope nesting and shadowing;
- mutability;
- storage requirement metadata;
- callable signature information required by Stage 05.

Logical identities must not equal reusable scratch slots by definition.

## Required tests

At minimum:

- internal function;
- foreign function;
- zero/one/multiple parameters;
- parameters across multiple functions;
- immutable/mutable local;
- nested shadowed local;
- loop variable;
- local arrays required by canonical Stage1.

## Capacity policy

Use bounded reusable current-function/scope tables. If capacity fails, measure the actual peak before increasing it.

## Exit state

S1 may remain `PARTIAL` because constants and instruction results belong to Stage 04.

Required evidence:

```text
PASS1_FUNCTIONS=PASS
PASS1_PARAMETERS=PASS
PASS1_LOCALS=PASS
PASS1_SCOPE_RESOLUTION=PASS
CANDIDATE_STAGE0_CHECK=PASS
S1=PARTIAL_EXPECTED
```

Re-check control before committing and before Stage 04.
