# S3C-NG IR Interchange V8

S3C-NG IR V8 preserves the V1-V7 wire contracts and adds an explicit generic
scalar `vector_push<T>` CALL target. The decoder validates the emitted type
descriptor and register identities; it does not infer the source operation or
repair mismatched metadata.

## V8 generic vector push

A CALL instruction with `operand0 = -3` is followed, after its ordered kind-6
argument records, by one kind-18 record:

```text
(18, function_index, instruction_index, builtin_id,
 element_type_descriptor_id, 0, 0, 0)
```

`builtin_id` is currently `1` for `vector_push<T>`. Its CALL has exactly two
arguments: a mutable reference to `vector<T>` and a value whose register type
is exactly `T`. `T` must be one of the currently supported scalar vector
elements: `i64`, `tryte`, or `f64`. The result is `tryte` when retained and may
be absent when the source discards it. The CALL instruction's immediate is
reserved and must be zero.

The decoder maps the validated operation to the existing canonical runtime
builtin (`i64_vector_push`, `tryte_vector_push`, or `f64_vector_push`). Record
and other composite element layouts are not represented by this V8 operation;
they remain rejected until the interchange carries their complete ordered
cell layout and the emitter can produce the corresponding operands.

## Compatibility

V1-V7 streams retain their existing meaning. V8 is required only when a stream
contains the `-3` CALL sentinel and kind-18 metadata. Older decoders reject the
new sentinel rather than treating it as a normal function index.
