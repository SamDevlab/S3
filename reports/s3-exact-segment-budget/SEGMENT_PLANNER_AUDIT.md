# Segment Planner and Runtime Audit

## Assembly structure

The planner is deterministic over `AssemblyFunction.blocks` and
`AssemblyBlock.instructions`. Each nonempty block is partitioned into
contiguous, gap-free index ranges. It closes a range after a `TCALL`,
conditional `TBR3`, unconditional `TJMP`, or `TRET`; the transfer/return stays
inside that range as its final logical instruction. The generated plan never
crosses block labels. The focused plan tests check coverage, ordering, weights,
barrier placement, and the fused `TCMP`/`TBR3` logical pair.

## Call and callback ordering

`TCALL` is the only Assembly call opcode. It can target an external function,
so synchronous callback re-entry is possible. A segment ending at `TCALL`
precharges only through the call itself. The callback therefore sees the same
logical count as the baseline at that boundary; the caller's next segment is
not charged until the call returns. The native test invokes an exported S3
function through a foreign callback and compares P0/P2 behavior.

## Internal helpers and failures

Emitter-generated helper calls for operations such as tryte min/max and
runtime-managed values are implementation details within a logical instruction
or `TCALL`; they do not read or write `__s3_instruction_count`, call user
callbacks, or re-enter S3. Repository search finds the counter referenced by
the emitter's check/increment sequences and by the runtime BSS definition only.
Classification: `RUNTIME_HELPER_BUDGET_OBSERVABILITY=NONE`.

Non-budget failures write a fixed category/context diagnostic and terminate
through the runtime failure path. They do not report the budget counter and do
not resume S3 execution. Consequently a fast segment's reserved count is not
observable after such a terminal failure through the supported runtime API.
The bounds-failure differential test exercises this path.

## Concurrency

The count-up field is a process-global BSS word with no atomic or locking
protocol. Exported shared-library functions can be called by a host, but the
repository does not promise thread-safe concurrent entry. If two host threads
do enter concurrently, P2's aggregate add can become visible earlier than P0's
per-instruction increments. That interleaving is not equivalent and remains
outside the experimental E0 scope. This is a documented qualification limit,
not an assertion that concurrency is impossible.
