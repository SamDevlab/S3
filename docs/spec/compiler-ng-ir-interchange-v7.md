# S3C-NG IR Interchange V7

S3C-NG IR V7 retains the V1-V6 record contracts and adds opcode 15 for scalar
relational expressions. Existing opcode IDs and record layouts are unchanged.

## Relational instruction

An instruction record for opcode 15 has the existing kind-4 layout:

```text
(4, function_index, 15, result_register, 2, left_register, right_register, relation_id)
```

The result register is `trit`; both operand registers have the same scalar type.
`relation_id` is one of:

| ID | Operator |
| --- | --- |
| 0 | `==` |
| 1 | `!=` |
| 2 | `<` |
| 3 | `<=` |
| 4 | `>` |
| 5 | `>=` |

The V7 decoder rejects opcode 15 in older format versions, unknown relation IDs,
missing result registers, and operand counts other than two. Runtime type
validation remains governed by the canonical S3 `RELATE` verifier contract.
