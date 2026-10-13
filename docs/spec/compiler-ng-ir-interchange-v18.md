# S3C-NG IR Interchange V18

S3C-NG IR V18 retains the V1-V17 contracts and adds typed unary negation.
Earlier streams remain decodable with their original meanings.

## Unary negation instruction

Opcode `20` uses the existing kind-4 instruction record:

```text
(4, function_index, 20, result_register, 1, operand_register, -1, 0)
```

The result and operand have the same scalar register type: `i64`, `f64`,
`trit`, or `tryte`. The decoder maps opcode `20` to canonical `INVERT`
semantics, which performs checked numeric negation for `i64`, floating-point
sign negation for `f64`, and balanced-ternary inversion for `trit` and `tryte`.
The opcode is valid only in V18 or later; V1-V17 streams containing opcode `20`
are rejected explicitly.
