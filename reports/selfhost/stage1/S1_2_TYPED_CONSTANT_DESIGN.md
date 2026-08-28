# S1.2 Typed Constant Identity

## Scope

This lane records typed constants in the canonical Stage1 semantic value
namespace. It does not add instruction operands, result edges, call dataflow,
terminator links, or canonical serialization.

## Factual candidate model

The candidate exposes `semantic_v2_value(value_id, function_id, kind,
type_code, anchor_start, anchor_length, mutable_flag, storage_id)`. Numeric
literal lowering creates a value with kind `3` (typed constant inline), takes
the type code from the existing type-name hash mapping, allocates from the
monotonic `value_count`, and records the literal token span. It uses no
storage slot for the semantic identity. The candidate materializes repeated
literal occurrences independently; S1.2 therefore does not add interning.

## Canonical record

`ir_semantic_value_records[value_id]` is the semantic table. Existing
parameter and local records remain at their established deterministic IDs.
Constants are collected in a separate, bounded constant-definition table and
receive IDs only after parameter/local allocation. The constant table index is
temporary storage and is never exposed as a value ID.

Each emitted constant has:

- kind `3`, using the existing S3IR2 typed-constant kind;
- the existing type code (`trit=1`, `tryte=2`, `i64=3`, `f64=4`);
- a monotonic semantic value ID after the binding IDs;
- the first defining function as definition owner;
- the source token start and length as its stable source anchor;
- no physical storage alias (`storage_id=-1`).

The semantic header uses the existing packed value-header domains: kind,
owner/global marker, type code, and literal payload. Definition metadata is
kept separately so the header payload remains the typed literal payload.

## Allocation and boundaries

Allocation is source-order deterministic and monotonic. A constant ID is
never derived from a token index, scratch slot, pointer, address, unordered
iteration, or accidental local-array position. The constant-definition table
is bounded by the existing semantic table's 365-record domain; no new
unbounded or speculative matrix is introduced. The final binding count
reserves the available suffix for constants. If all occurrences do not fit
after that reservation, the pipeline fails closed and the diagnostic view
exposes only the valid suffix, never an out-of-domain ID. Capacity exhaustion
is a hard failure.

## Fail-closed rules

An unresolved type, unsupported literal representation, invalid range, bad
source span, or exhausted semantic capacity marks the pipeline invalid. No
unknown constant receives a default type or value ID. Existing parser,
semantic, capacity, and emitter blockers remain authoritative; S1.2 does not
make the general emitter appear complete.

## Verification view

For already-blocked compilation paths only, a deterministic diagnostic view
reports the constant ID, definition owner, type code, literal, and source
anchor. It is not a second IR implementation and is not used by the
production emitter. S1.3 will consume these IDs when it adds def/use edges.
