# S3C-NG IR Interchange V23

V23 adds source-semantic descriptors for the existing `host_capability` and
`resource_handle` types. They are represented by type kinds 11 and 12 in the
kind-12/kind-13 type-descriptor records. Their descriptor IDs are respectively
7 and 8; the first six IDs retain the V3 primitive descriptor contract.

Both descriptors use the primitive descriptor field layout: source spans,
element type, target type, mutability, and field range are unset, and reserved
cells are zero. V23 rejects these kinds in earlier stream versions and rejects
them at any descriptor ID other than the IDs assigned above.

At the canonical IR boundary both source types map to `IRType.I64`, matching
the Python frontend's existing lowering. Their distinct descriptors remain
available to S3C-NG semantic analysis so host/resource builtin signatures and
references are checked before lowering. This extension does not change runtime
representation or builtin execution.

All earlier V22 event records and their validation rules remain unchanged.
