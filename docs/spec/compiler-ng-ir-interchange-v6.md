# S3C-NG IR Interchange V6

S3C-NG IR is a flat sequence of signed 64-bit records with width eight. V6
retains the V1-V5 record contracts and adds an explicit target record for the
generic scalar-vector length builtin.

## Generic `vector_len<T>` call

A CALL instruction uses callee sentinel `-2` and is followed, after its CALL
argument records, by kind 17:

```text
(17, function_index, instruction_index, builtin_id, element_type_id, 0, 0, 0)
```

`builtin_id` is `1` for `vector_len<T>`. The decoder requires exactly one
argument whose register type is a reference descriptor targeting a vector
descriptor with the same `element_type_id`. The result register must have the
builtin i64 type. Supported element descriptors are i64, tryte, and f64, which
are mapped to the existing canonical runtime calls; the record does not infer
types or synthesize reference semantics.

The V5 `vector_new<T>` sentinel `-1` and kind-16 record remain unchanged. V1-V5
streams retain their previous interpretation. Unsupported generic builtins,
element types, or descriptor mismatches fail closed.
