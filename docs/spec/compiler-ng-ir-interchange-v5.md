# S3C-NG IR Interchange V5

S3C-NG IR is a flat sequence of signed 64-bit records with width eight. V5
preserves the V1-V4 records and adds one explicit generic-call target record
for scalar vector allocation.

## V5 Generic Vector Allocation

A CALL whose `operand0` is `-1` is a builtin target, not a function index. After
its contiguous kind-6 argument records, it must have exactly one kind-16 record:

```text
(16, function_index, instruction_index, builtin_id, element_type_id, 0, 0, 0)
```

The stable builtin IDs are:

| ID | Canonical runtime callee | Required element descriptor kind |
| --- | --- | --- |
| 1 | `i64_vector_new` | i64 (kind 1) |
| 2 | `tryte_vector_new` | tryte (kind 3) |
| 3 | `f64_vector_new` | f64 (kind 4) |

The decoder validates that the CALL has one i64 capacity argument and that
its result register has a vector descriptor whose element ID matches the
record. It then maps the explicit builtin ID to the canonical runtime callee;
it does not infer or repair the source-level type.

V1-V4 streams retain their previous interpretation. V5 does not yet encode
generic vector operations, vectors of records, or reference semantics; those
remain separate compiler capabilities.
