# Artifact migration 0.5 to 0.6

Status: normative for the aggregate-result campaign.

IR JSON and S3 Assembly writers now emit version `0.6.0`. Readers continue to
accept valid `0.5.0` artifacts when every function and instruction remains
width-1.

## IR JSON

Version `0.6.0` makes result groups explicit:

- functions carry `result_types`;
- producer instructions carry `results`;
- `return_type` remains as the first result cell for width-1 compatibility;
- `result` remains as the singular spelling when `results` has one cell.

Legacy `0.5.0` IR is normalized to `result_types = [return_type]` and
`results = [result]`. A `0.5.0` artifact that includes `result_types` or
`results` is rejected because it is using 0.6-only fields under the old header.

## S3 Assembly

Version `0.6.0` keeps the scalar spelling and adds group spelling:

```asm
.function scalar -> tryte
    TRET r0

.function aggregate -> [tryte, trit]
    TRET [r0, r1]

TCALL [r2, r3], aggregate
TCALL [], aggregate
```

Legacy `.s3asm 0.5.0` remains width-1 only. A 0.5 file using result type lists,
`TCALL` destination lists, or `TRET` operand lists is rejected.

## Runtime and ABI

The source language still returns one logical value. Aggregate values are
lowered to ordered result cells. Width-1 native returns use `RAX`; width > 1 uses
a caller-owned hidden sret area internal to the x86-64 backend. The hidden
pointer is not part of the source language, IR, or S3 Assembly surface.

No heap, exceptions, tuple source returns, partial result consumption, or C ABI
promise is introduced by this migration.
